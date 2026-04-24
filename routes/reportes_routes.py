from flask import Blueprint, request, jsonify, send_file
import io
import os
import pandas as pd
import traceback
from datetime import datetime, date
from sqlalchemy import func 
from extensions import db
from models.pago import Pago
from models.alumno import Alumno
from models.estructura_pago import EstructuraPago
from models.grupo import Grupo 
from helpers import registrar_accion, obtener_id_admin
import subprocess

# 🔥 IMPORTAMOS ZONEINFO PARA FORZAR HORA DE MÉXICO EN TODO EL ARCHIVO
from zoneinfo import ZoneInfo 

# 🛡️ IMPORTAMOS EL ESCUDO DE SEGURIDAD
from flask_jwt_extended import verify_jwt_in_request, get_jwt

# --- EXCEL PRO ---
from openpyxl.styles import Font, PatternFill, Alignment

# --- PDF PRO ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT 

reportes_bp = Blueprint('reportes_bp', __name__)

# 🔥 RUTA DEL LOGO
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUTA_LOGO = os.path.join(BASE_DIR, 'static', 'img', 'LOGO3.png')

print(f"\n--- 🔍 REVISANDO LOGO EN: {RUTA_LOGO} ---")
if os.path.exists(RUTA_LOGO):
    print("✅ LOGO ENCONTRADO\n")
else:
    print("❌ LOGO NO ENCONTRADO - Revisa la carpeta static/img\n")

def limpiar_param(val):
    if val in [None, "null", "undefined", "", "Todos", "0"]: return None
    return val

# 🕒 FUNCIONES MAESTRAS PARA OBTENER LA HORA DE MÉXICO EN ESTE ARCHIVO
def ahora_mx():
    return datetime.now(ZoneInfo("America/Mexico_City"))

def hoy_mx():
    return ahora_mx().date()

# --- 1. PIE DE PÁGINA ---
def pie_de_pagina(canvas, doc):
    canvas.saveState()
    estilos = getSampleStyleSheet()
    texto = f"SISTEMA DE CONTROL DE PAGOS  —  Página {doc.page}"
    p = Paragraph(f"<font color='grey' size=8>{texto}</font>", estilos['Normal'])
    p.wrapOn(canvas, letter[0], 50)
    p.drawOn(canvas, letter[0]/2 - 80, 20)
    canvas.restoreState()

# --- 2. ENCABEZADO OFICIAL (ALINEACIÓN PERFECTA) ---
def crear_encabezado_logo(elementos, titulo_reporte, estilos):
    try:
        if os.path.exists(RUTA_LOGO):
            img = Image(RUTA_LOGO, width=65, height=65) 
        else:
            img = ""
    except: img = ""

    estilo_escuela = estilos['Title']
    estilo_escuela.fontSize = 17
    estilo_escuela.alignment = TA_LEFT
    estilo_escuela.leftIndent = 0 
    estilo_escuela.textColor = colors.HexColor("#0f172a")
    estilo_escuela.spaceAfter = 2

    estilo_sistema = estilos['Heading2']
    estilo_sistema.fontSize = 11
    estilo_sistema.alignment = TA_LEFT
    estilo_sistema.leftIndent = 0
    estilo_sistema.textColor = colors.HexColor("#64748b")
    estilo_sistema.spaceAfter = 6

    estilo_tipo_reporte = estilos['Normal']
    estilo_tipo_reporte.fontSize = 12
    estilo_tipo_reporte.fontName = 'Helvetica-Bold'
    estilo_tipo_reporte.alignment = TA_LEFT
    estilo_tipo_reporte.leftIndent = 0
    estilo_tipo_reporte.textColor = colors.HexColor("#1d4ed8") 
    estilo_tipo_reporte.spaceAfter = 2

    estilo_fecha = estilos['Normal']
    estilo_fecha.fontSize = 9
    estilo_fecha.leftIndent = 0
    estilo_fecha.textColor = colors.grey

    data = [[img, [
        Paragraph("<b>EPC JUAN MIRANDA URESTI N°16</b>", estilo_escuela),
        Paragraph("SISTEMA DE CONTROL DE PAGOS", estilo_sistema),
        Paragraph(f"{titulo_reporte}", estilo_tipo_reporte),
        Paragraph(f"Fecha de reporte: {ahora_mx().strftime('%d/%m/%Y %H:%M')}", estilo_fecha)
    ]]]

    t = Table(data, colWidths=[70, 460])
    t.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (0,0), 0), 
        ('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor("#1E293B")),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
    ]))
    
    elementos.append(t)
    elementos.append(Spacer(1, 15))

# --- 3. MOTOR PDF DEUDORES ---
def generar_pdf_deudores_pro(data_agrupada, titulo_str, nombre_archivo, mensaje_vacio="No hay registros."):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=titulo_str,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    estilos = getSampleStyleSheet()
    elementos = []
    crear_encabezado_logo(elementos, titulo_str, estilos)
    
    if not data_agrupada:
        # 🔥 MENSAJE ELEGANTE SI NO HAY DATOS
        estilo_aviso = estilos['Normal']
        estilo_aviso.fontSize = 12
        estilo_aviso.textColor = colors.HexColor("#475569") # Gris oscuro
        elementos.append(Paragraph(f"<i>{mensaje_vacio}</i>", estilo_aviso))
    else:
        total_general = 0
        estilo_nombre = estilos['Normal']
        estilo_nombre.fontSize = 11
        estilo_nombre.leftIndent = 0

        for alu in data_agrupada:
            bloque = []
            nombre_str = f"<font color='#0f172a'><b>{alu['Alumno']}</b></font> — <font color='#b91c1c'><b>{alu['Matrícula']}</b></font>"
            bloque.append(Paragraph(nombre_str, estilo_nombre))
            bloque.append(Spacer(1, 5))
            
            tabla_data = [["Concepto", "Monto Restante"]] 
            for c in alu["Conceptos"]:
                tabla_data.append([c["concepto"], "${:,.2f}".format(c["monto"])])
            tabla_data.append(["TOTAL ADEUDO", "${:,.2f}".format(alu['Total'])])
            total_general += alu["Total"]
            
            t = Table(tabla_data, colWidths=[460, 70], hAlign='LEFT')
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b91c1c")), 
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke),
                ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#b91c1c")),
            ]))
            bloque.append(t)
            bloque.append(Spacer(1, 15))
            elementos.append(KeepTogether(bloque))
            
        elementos.append(Spacer(1, 20))
        estilo_total = estilos['Normal']
        estilo_total.fontSize = 12
        elementos.append(Paragraph(f"<b>TOTAL GENERAL DE ADEUDOS: ${total_general:,.2f}</b>", estilo_total))
    
    doc.build(elementos, onFirstPage=pie_de_pagina, onLaterPages=pie_de_pagina)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)

# --- 4. MOTOR PDF GENÉRICO CON TOTALIZADOR ---
def generar_pdf_generico_pro(titulo_str, data, color_tema, nombre_archivo, total_suma=None, titulo_total="TOTAL", mensaje_vacio="No se encontraron registros."):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=titulo_str,
                            rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    estilos = getSampleStyleSheet()
    elementos = []
    crear_encabezado_logo(elementos, titulo_str, estilos)
    
    if not data:
        # 🔥 MENSAJE ELEGANTE SI NO HAY DATOS
        estilo_aviso = estilos['Normal']
        estilo_aviso.fontSize = 12
        estilo_aviso.textColor = colors.HexColor("#475569")
        elementos.append(Paragraph(f"<i>{mensaje_vacio}</i>", estilo_aviso))
    else:
        headers = list(data[0].keys())
        cuerpo = [headers]
        for d in data: cuerpo.append([str(valor) for valor in d.values()])
        
        anchos = [530 / len(headers)] * len(headers)
        if "Folio" in headers and "Concepto" in headers:
            anchos = [60, 200, 200, 70] 
        elif "Fecha" in headers and "Monto" in headers:
            anchos = [70, 195, 195, 70] 
        elif "Matrícula" in headers and "Estatus" in headers:
            anchos = [80, 350, 100]    

        t = Table(cuerpo, colWidths=anchos, hAlign='LEFT') 
        
        estilo_tabla = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_tema),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")), 
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,1), (-1,-1), colors.black), 
        ])
        
        for i in range(1, len(cuerpo)):
            bg_color = colors.HexColor("#f8fafc") if i % 2 == 0 else colors.white
            estilo_tabla.add('BACKGROUND', (0,i), (-1,i), bg_color)

        t.setStyle(estilo_tabla)
        elementos.append(t)
        
        # AGREGAMOS EL BLOQUE DEL TOTAL COMO EN DEUDORES
        if total_suma is not None:
            elementos.append(Spacer(1, 20))
            estilo_total = estilos['Normal']
            estilo_total.fontSize = 12
            elementos.append(Paragraph(f"<b>{titulo_total}: ${total_suma:,.2f}</b>", estilo_total))
        
    doc.build(elementos, onFirstPage=pie_de_pagina, onLaterPages=pie_de_pagina)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)

# --- 5. EXCEL PRO ---
def generar_excel(data, nombre_hoja, nombre_archivo, mensaje_vacio="No hay información para mostrar"):
    # 🔥 AHORA EL EXCEL TAMBIÉN MUESTRA UN AVISO ELEGANTE
    df = pd.DataFrame(data) if data else pd.DataFrame([{"Aviso": mensaje_vacio}])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
        ws = writer.sheets[nombre_hoja]
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True)
        for col_idx, column in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill, cell.font, cell.alignment = header_fill, header_font, Alignment(horizontal="center")
            max_len = max(df[column].astype(str).map(len).max(), len(str(column))) + 4
            ws.column_dimensions[ws.cell(row=1, column=col_idx).column_letter].width = max_len
        ws.auto_filter.ref = ws.dimensions
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=nombre_archivo)

# ==========================================
#                ENDPOINTS
# ==========================================

@reportes_bp.route("/reportes/dashboard", methods=["GET", "OPTIONS"])
def dashboard_ingresos():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        hoy = hoy_mx(); p_mes = hoy.replace(day=1)
        
        pagos_hoy = db.session.query(Pago, EstructuraPago).join(EstructuraPago).filter(
            Pago.fecha_pago == hoy, Pago.estado.in_(['PAGADO', 'PARCIAL'])).all()
            
        pagos_mes = db.session.query(Pago, EstructuraPago).join(EstructuraPago).filter(
            Pago.fecha_pago >= p_mes, Pago.fecha_pago <= hoy, Pago.estado.in_(['PAGADO', 'PARCIAL'])).all()

        suma_hoy = sum([float(p.monto_abonado) if p.monto_abonado else float(e.monto or 0) for p, e in pagos_hoy])
        suma_mes = sum([float(p.monto_abonado) if p.monto_abonado else float(e.monto or 0) for p, e in pagos_mes])

        return jsonify({"ingresos_hoy": suma_hoy, "ingresos_mes": suma_mes})
    except Exception as e: return jsonify({"error": "Dashboard error"}), 500


@reportes_bp.route("/reportes/corte-caja", methods=["GET", "OPTIONS"])
def corte_caja():
    if request.method == "OPTIONS": return jsonify({}), 200

    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "Solo administradores pueden descargar el corte de caja"}), 403

    try:
        formato = request.args.get('formato', 'pdf')
        hoy = hoy_mx()
        
        pagos = db.session.query(Pago, Alumno, EstructuraPago).select_from(Pago).join(Alumno).join(EstructuraPago).filter(Pago.fecha_pago == hoy).all()
        
        def formato_folio(p):
            folio_str = str(p.folio or "S/F")
            if p.estado == 'PARCIAL': return folio_str
            return folio_str.split('(')[0].strip()

        data = []
        total_suma = 0 
        for p, a, e in pagos:
            monto_real = float(p.monto_abonado) if p.monto_abonado else float(e.monto or 0)
            if p.estado == 'PAGADO' or monto_real > 0:
                total_suma += monto_real
                data.append({
                    "Folio": formato_folio(p), 
                    "Alumno": f"{a.apellido} {a.nombre}".upper(), 
                    "Concepto": e.concepto, 
                    "Monto": "${:,.2f}".format(monto_real)
                })
        
        try: registrar_accion(operador.get('id'), "DESCARGA_CORTE_CAJA", f"Descargó el Corte de Caja del día de hoy en formato {formato.upper()}")
        except: pass

        mensaje_vacio = "No existen ingresos registrados para el día de hoy." # 🔥 Mensaje personalizado

        if formato == 'excel': 
            if data: data.append({"Folio": "", "Alumno": "", "Concepto": "TOTAL DEL DÍA", "Monto": "${:,.2f}".format(total_suma)})
            return generar_excel(data, "Corte", f"Corte_{hoy}.xlsx", mensaje_vacio)
            
        return generar_pdf_generico_pro(f"CORTE DE CAJA DIARIO", data, colors.HexColor("#1E293B"), "Corte.pdf", total_suma=total_suma, titulo_total="TOTAL INGRESOS DEL DÍA", mensaje_vacio=mensaje_vacio)
    except Exception as e: return jsonify({"error": str(e)}), 500


@reportes_bp.route("/reportes/ingresos", methods=["GET", "OPTIONS"])
def reporte_ingresos():
    if request.method == "OPTIONS": return jsonify({}), 200

    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para descargar este reporte"}), 403

    try:
        inicio = request.args.get('inicio')
        fin = request.args.get('fin')
        formato = request.args.get('formato', 'pdf')
        
        try: registrar_accion(operador.get('id'), "DESCARGA_INGRESOS", f"Descargó histórico de ingresos ({inicio} a {fin}) en formato {formato.upper()}")
        except: pass

        pagos = db.session.query(Pago, Alumno, EstructuraPago).select_from(Pago).join(Alumno).join(EstructuraPago).filter(Pago.fecha_pago.between(inicio, fin)).all()
        
        data = []
        total_suma = 0 
        for p, a, e in pagos:
            monto_real = float(p.monto_abonado) if p.monto_abonado else float(e.monto or 0)
            if p.estado == 'PAGADO' or monto_real > 0:
                total_suma += monto_real
                data.append({
                    "Fecha": p.fecha_pago.strftime("%d/%m/%Y"), 
                    "Alumno": f"{a.apellido} {a.nombre}".upper(), 
                    "Concepto": e.concepto, 
                    "Monto": "${:,.2f}".format(monto_real)
                })
        
        mensaje_vacio = f"No existen ingresos registrados en el periodo del {inicio} al {fin}." # 🔥 Mensaje personalizado

        if formato == 'excel': 
            if data: data.append({"Fecha": "", "Alumno": "", "Concepto": "TOTAL INGRESOS", "Monto": "${:,.2f}".format(total_suma)})
            return generar_excel(data, "Ingresos", "Historico_Ingresos.xlsx", mensaje_vacio)
            
        return generar_pdf_generico_pro(f"HISTÓRICO DE INGRESOS ({inicio} al {fin})", data, colors.HexColor("#1E293B"), "Historico.pdf", total_suma=total_suma, titulo_total="TOTAL GENERAL DE INGRESOS", mensaje_vacio=mensaje_vacio)
    except Exception as e: return jsonify({"error": str(e)}), 500


@reportes_bp.route("/reportes/deudores", methods=["GET", "OPTIONS"])
def reporte_deudores():
    if request.method == "OPTIONS": return jsonify({}), 200

    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    id_gen = limpiar_param(request.args.get('generacion'))
    if not id_gen: return jsonify({"error": "Falta Gen"}), 400

    try:
        id_grupo = limpiar_param(request.args.get('grupo')); sem = limpiar_param(request.args.get('semestre')); formato = request.args.get('formato', 'pdf')
        
        try: registrar_accion(operador.get('id'), "DESCARGA_DEUDORES", f"Descargó reporte de deudores (Gen: {id_gen}, Grupo: {id_grupo or 'Todos'}, Sem: {sem or 'Todos'}) en formato {formato.upper()}")
        except: pass

        query = Alumno.query.filter(Alumno.id_generacion == int(id_gen), Alumno.estatus.in_(['ACTIVO', 'BAJA']))
        if id_grupo: query = query.join(Grupo).filter(Grupo.nombre_grupo == id_grupo)
        if sem: query = query.filter(Alumno.semestre_actual == int(sem))
        alumnos = query.all(); alu_dict = {}
        
        hoy = hoy_mx() 
        
        for a in alumnos:
            f_limite = a.fecha_baja if (a.estatus == 'BAJA' and a.fecha_baja) else hoy
            pagos = db.session.query(Pago, EstructuraPago).join(EstructuraPago).filter(Pago.id_alumno == a.id_alumno, Pago.estado.in_(['PENDIENTE', 'PARCIAL'])).all()
            for p, e in pagos:
                if (e.semestre or 1) <= (a.semestre_actual or 1):
                    vencido = False
                    if e.anio and e.mes:
                        if e.anio < f_limite.year or (e.anio == f_limite.year and e.mes <= f_limite.month): vencido = True
                    else: vencido = (a.estatus != 'BAJA')
                    if vencido:
                        deuda = float(e.monto) - float(p.monto_abonado or 0)
                        if deuda > 0:
                            if a.id_alumno not in alu_dict:
                                nom = f"{a.apellido} {a.nombre}".upper() + (" [BAJA]" if a.estatus == 'BAJA' else "")
                                alu_dict[a.id_alumno] = {"Matrícula": a.matricula, "Alumno": nom, "Conceptos": [], "Total": 0}
                            alu_dict[a.id_alumno]["Conceptos"].append({"concepto": e.concepto, "monto": deuda})
                            alu_dict[a.id_alumno]["Total"] += deuda
        
        data = list(alu_dict.values())
        
        # ✅ ELIMINAMOS EL RETORNO DE ERROR 404 PARA QUE DESCARGUE EL PDF VACÍO
        mensaje_vacio = "No se encontraron alumnos con adeudos pendientes para los filtros seleccionados." # 🔥 Mensaje personalizado
        titulo = f"ALUMNOS CON DEUDAS" + (f" - {sem}° SEM" if sem else "")

        if formato == 'excel':
            excel_data = [{"Matrícula": x["Matrícula"], "Alumno": x["Alumno"], "Adeudo": x["Total"]} for x in data] if data else []
            return generar_excel(excel_data, "Deudores", "Deudores.xlsx", mensaje_vacio)
        
        return generar_pdf_deudores_pro(data, titulo, "Deudores.pdf", mensaje_vacio)
    except Exception as e: return jsonify({"error": str(e)}), 500


@reportes_bp.route("/reportes/al-corriente", methods=["GET", "OPTIONS"])
def reporte_al_corriente():
    if request.method == "OPTIONS": return jsonify({}), 200

    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    id_gen = limpiar_param(request.args.get('generacion'))
    try:
        id_grupo = limpiar_param(request.args.get('grupo')); sem = limpiar_param(request.args.get('semestre')); formato = request.args.get('formato', 'pdf')
        
        try: registrar_accion(operador.get('id'), "DESCARGA_AL_CORRIENTE", f"Descargó reporte de alumnos al corriente (Gen: {id_gen}, Grupo: {id_grupo or 'Todos'}, Sem: {sem or 'Todos'})")
        except: pass

        query = Alumno.query.filter(Alumno.id_generacion == int(id_gen), Alumno.estatus == 'ACTIVO')
        if id_grupo: query = query.join(Grupo).filter(Grupo.nombre_grupo == id_grupo)
        if sem: query = query.filter(Alumno.semestre_actual == int(sem))
        
        alumnos = query.all(); data = []
        hoy = hoy_mx()
        
        for a in alumnos:
            tiene_deuda = False
            pagos = db.session.query(Pago, EstructuraPago).join(EstructuraPago).filter(Pago.id_alumno == a.id_alumno, Pago.estado != 'PAGADO').all()
            for p, e in pagos:
                if (e.semestre or 1) <= (a.semestre_actual or 1):
                    if e.anio and e.mes:
                        if e.anio < hoy.year or (e.anio == hoy.year and e.mes <= hoy.month): tiene_deuda = True; break
                    else: tiene_deuda = True; break
            if not tiene_deuda:
                data.append({"Matrícula": a.matricula, "Alumno": f"{a.apellido} {a.nombre}".upper(), "Estatus": "AL CORRIENTE"})
        
        # ✅ NO HAY 404. SE GENERA DOCUMENTO.
        mensaje_vacio = "Actualmente no hay alumnos al corriente en sus pagos bajo los filtros seleccionados." # 🔥 Mensaje personalizado
        titulo = f"ALUMNOS AL CORRIENTE" + (f" - {sem}° SEM" if sem else "")
        
        if formato == 'excel': 
            return generar_excel(data, "Al Corriente", "Alumnos_Al_Corriente.xlsx", mensaje_vacio)
            
        return generar_pdf_generico_pro(titulo, data, colors.HexColor("#1E293B"), "Al_Corriente.pdf", mensaje_vacio=mensaje_vacio)
    except Exception as e: return jsonify({"error": str(e)}), 500


@reportes_bp.route("/reportes/respaldo", methods=["GET", "OPTIONS"])
def respaldo_db():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede generar respaldos físicos de la base de datos"}), 403

    DB_HOST = 'localhost'
    DB_USER = 'root'    
    DB_PASS = ''        
    DB_NAME = 'sistema_prepajmu' 

    ruta_mysqldump = r"C:\xampp\mysql\bin\mysqldump.exe" 
    
    if DB_PASS == '':
        comando = f"{ruta_mysqldump} -h {DB_HOST} -u {DB_USER} {DB_NAME}"
    else:
        comando = f"{ruta_mysqldump} -h {DB_HOST} -u {DB_USER} -p{DB_PASS} {DB_NAME}"

    try:
        proceso = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        salida, error = proceso.communicate()

        if proceso.returncode != 0:
            print(f"❌ ERROR DE MYSQLDUMP: {error.decode('utf-8', errors='ignore')}")
            return jsonify({"error": "No se pudo crear el respaldo. Revisa la consola."}), 500

        buffer = io.BytesIO(salida)
        buffer.seek(0)
        
        fecha_str = ahora_mx().strftime("%d_%m_%Y_%H%M")
        nombre_archivo = f"Respaldo_Prepa_{fecha_str}.sql"

        try: registrar_accion(operador.get('id'), "RESPALDO_BD", "Descargó un respaldo técnico completo (.sql) de la base de datos.")
        except: pass

        return send_file(buffer, as_attachment=True, download_name=nombre_archivo, mimetype='application/sql')

    except Exception as e: 
        return jsonify({"error": str(e)}), 500