from flask import Blueprint, request, jsonify, send_file
import io
import pandas as pd
import traceback
from datetime import datetime, date
from sqlalchemy import func # 🚩 Necesario para sumar el dinero
from extensions import db
from models.pago import Pago
from models.alumno import Alumno
from models.estructura_pago import EstructuraPago
from models.grupo import Grupo 

# ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER # 🚩 Necesario para centrar subtítulos

reportes_bp = Blueprint('reportes_bp', __name__)

# --- 0. ENDPOINT DEL DASHBOARD (DINERO REAL) ---
@reportes_bp.route("/dashboard", methods=["GET"])
def dashboard_ingresos():
    try:
        hoy_db = date.today()
        primer_dia_mes = hoy_db.replace(day=1)

        # Sumar ingresos de HOY
        suma_hoy = db.session.query(func.sum(EstructuraPago.monto)).select_from(Pago)\
            .join(EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura)\
            .filter(Pago.fecha_pago == hoy_db).scalar()

        # Sumar ingresos del MES
        suma_mes = db.session.query(func.sum(EstructuraPago.monto)).select_from(Pago)\
            .join(EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura)\
            .filter(Pago.fecha_pago >= primer_dia_mes, Pago.fecha_pago <= hoy_db).scalar()

        return jsonify({
            "ingresos_hoy": float(suma_hoy or 0),
            "ingresos_mes": float(suma_mes or 0)
        })
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Error al cargar dashboard"}), 500

# --- 1. MOTOR DE PDF DETALLADO (PARA DEUDORES) ---
def generar_pdf_deudores_pro(data_agrupada, titulo_str, nombre_archivo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    estilos = getSampleStyleSheet()
    elementos = []

    # 🚩 Estilos corregidos para que el título salga centrado y limpio
    title_style = estilos['Title']
    title_style.fontName = 'Helvetica-Bold'

    sub_header_style = estilos['Heading2']
    sub_header_style.alignment = TA_CENTER
    sub_header_style.backColor = None
    sub_header_style.fontName = 'Helvetica-Bold'
    sub_header_style.fontSize = 14
    sub_header_style.spaceAfter = 10

    date_style = estilos['Normal']
    date_style.alignment = TA_CENTER

    elementos.append(Paragraph("<b>SISTEMA DE CONTROL DE PAGOS</b>", title_style))
    elementos.append(Paragraph(f"<b>{titulo_str}</b>", sub_header_style))
    elementos.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", date_style))
    elementos.append(Spacer(1, 20))

    total_general = 0
    for alumno in data_agrupada:
        elementos.append(Paragraph(
            f"<b>{alumno['Alumno']}</b> — <font color='#b91c1c'>{alumno['Matrícula']}</font> ({alumno['Cantidad']} adeudos)",
            estilos['Heading3']
        ))
        elementos.append(Spacer(1, 5))

        tabla_data = [["Concepto", "Monto"]]
        for c in alumno["Conceptos"]:
            tabla_data.append([c["concepto"], "${:,.2f}".format(c["monto"])])

        tabla_data.append(["TOTAL ADEUDO ALUMNO", "${:,.2f}".format(alumno['Total'])])
        total_general += alumno["Total"]

        t = Table(tabla_data, colWidths=[350, 80], hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#b91c1c")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke),
            ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#b91c1c")),
        ]))
        elementos.append(t)
        elementos.append(Spacer(1, 15))

    elementos.append(Spacer(1, 20))
    elementos.append(Paragraph(
        f"<div align='right'><b>TOTAL GENERAL DE ADEUDOS: ${total_general:,.2f}</b></div>",
        estilos['Heading2']
    ))

    doc.build(elementos)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)

# --- 2. MOTOR DE PDF GENÉRICO (CORTE, INGRESOS, CORRIENTE) ---
def generar_pdf_generico_pro(titulo_str, data, color_tema, nombre_archivo):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    estilos = getSampleStyleSheet()
    
    elementos = [
        Paragraph("<b>SISTEMA DE CONTROL DE PAGOS</b>", estilos['Title']),
        Paragraph(f"<b>{titulo_str}</b>", estilos['Heading2']),
        Paragraph(f"Fecha de reporte: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilos['Normal']),
        Spacer(1, 20)
    ]

    if not data:
        elementos.append(Paragraph("No se encontraron registros.", estilos['Normal']))
    else:
        headers = list(data[0].keys())
        cuerpo = [headers]
        for d in data:
            cuerpo.append([str(valor) for valor in d.values()])
            
        if "Monto" in headers:
            col_idx = headers.index("Monto")
            total = sum(float(d[headers[col_idx]]) for d in data)
            fila_total = [""] * len(headers); fila_total[0] = "TOTAL"; fila_total[col_idx] = "${:,.2f}".format(total)
            cuerpo.append(fila_total)

        t = Table(cuerpo, hAlign='CENTER', colWidths=[80, 220, 130, 80])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), color_tema),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BACKGROUND', (0,-1), (-1,-1), colors.whitesmoke)
        ]))
        elementos.append(t)

    doc.build(elementos)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=nombre_archivo)

# --- 3. FUNCIÓN AUXILIAR EXCEL ---
def generar_excel(data, nombre_hoja, nombre_archivo):
    df = pd.DataFrame(data) if data else pd.DataFrame([{"Mensaje": "Sin datos"}])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=nombre_hoja)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=nombre_archivo)

# ==========================================
# ENDPOINTS DE DESCARGA
# ==========================================

@reportes_bp.route("/corte-caja", methods=["GET"])
def corte_caja():
    try:
        formato = request.args.get('formato', 'pdf')
        hoy_db = date.today()
        pagos = db.session.query(Pago, Alumno, EstructuraPago).select_from(Pago)\
            .join(Alumno, Pago.id_alumno == Alumno.id_alumno)\
            .join(EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura)\
            .filter(Pago.fecha_pago == hoy_db)\
            .order_by(Alumno.apellido, Alumno.nombre).all()
        
        data = [{"Folio": p.folio or "S/F", "Alumno": f"{a.apellido} {a.nombre}".upper(), "Concepto": e.concepto, "Monto": float(e.monto)} for p, a, e in pagos]
        if formato == 'excel':
            return generar_excel(data, "Corte Diario", f"Corte_{hoy_db}.xlsx")
        return generar_pdf_generico_pro(f"Corte de Caja Diario - {hoy_db}", data, colors.HexColor("#15803d"), "Corte_Hoy.pdf")
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Error interno"}), 500

@reportes_bp.route("/deudores", methods=["GET"])
def reporte_deudores():
    id_gen = request.args.get('generacion')
    if not id_gen or id_gen in ["null", "undefined", ""]:
        return jsonify({"error": "Debe seleccionar una generación"}), 400
    try:
        id_gen = int(id_gen); id_grupo = request.args.get('grupo'); formato = request.args.get('formato', 'pdf')
        query = db.session.query(Alumno, Pago, EstructuraPago).select_from(Alumno)\
            .join(Pago, Alumno.id_alumno == Pago.id_alumno)\
            .join(EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura)\
            .filter(Alumno.id_generacion == id_gen, Pago.estado == 'PENDIENTE')\
            .order_by(Alumno.apellido, Alumno.nombre)
        if id_grupo and id_grupo not in ["", "null", "undefined"]:
            query = query.join(Grupo, Alumno.id_grupo == Grupo.id_grupo).filter(Grupo.nombre_grupo == id_grupo)
        resultados = query.all()
        
        alumnos_dict = {}
        for a, p, e in resultados:
            key = a.id_alumno
            if key not in alumnos_dict:
                alumnos_dict[key] = {"Matrícula": a.matricula, "Alumno": f"{a.apellido} {a.nombre}".upper(), "Conceptos": [], "Total": 0}
            alumnos_dict[key]["Conceptos"].append({"concepto": e.concepto, "monto": float(e.monto), "orden": (getattr(e, 'anio', 0), getattr(e, 'mes', 0))})
            alumnos_dict[key]["Total"] += float(e.monto)
            
        data_agrupada = list(alumnos_dict.values())
        for alu in data_agrupada:
            alu["Conceptos"].sort(key=lambda x: x["orden"])
            alu["Cantidad"] = len(alu["Conceptos"])
            
        if formato == 'excel':
            excel_flat = [{"Matrícula": al["Matrícula"], "Alumno": al["Alumno"], "Concepto": co["concepto"], "Monto": co["monto"]} for al in data_agrupada for co in al["Conceptos"]]
            return generar_excel(excel_flat, "Deudores", "Deudores.xlsx")
        return generar_pdf_deudores_pro(data_agrupada, "REPORTE DETALLADO DE ALUMNOS CON DEUDAS", "Deudores.pdf")
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Error interno"}), 500

@reportes_bp.route("/ingresos", methods=["GET"])
def reporte_ingresos():
    try:
        inicio = request.args.get('inicio'); fin = request.args.get('fin'); formato = request.args.get('formato', 'pdf')
        if not inicio or not fin: return jsonify({"error": "Fechas requeridas"}), 400
        pagos = db.session.query(Pago, Alumno, EstructuraPago).select_from(Pago)\
            .join(Alumno, Pago.id_alumno == Alumno.id_alumno)\
            .join(EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura)\
            .filter(Pago.fecha_pago.between(inicio, fin))\
            .order_by(Alumno.apellido, Alumno.nombre).all()
            
        data = [{"Fecha": p.fecha_pago.strftime("%d/%m/%Y"), "Alumno": f"{a.apellido} {a.nombre}".upper(), "Concepto": e.concepto, "Monto": float(e.monto)} for p, a, e in pagos]
        if formato == 'excel': return generar_excel(data, "Histórico", "Ingresos.xlsx")
        return generar_pdf_generico_pro(f"Histórico de Ingresos ({inicio} a {fin})", data, colors.HexColor("#2563eb"), "Historico.pdf")
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Error interno"}), 500

@reportes_bp.route("/al-corriente", methods=["GET"])
def reporte_al_corriente():
    try:
        id_gen = request.args.get('generacion')
        if not id_gen or id_gen in ["null", "undefined", ""]: return jsonify({"error": "Seleccione generación"}), 400
        id_gen = int(id_gen); id_grupo = request.args.get('grupo'); formato = request.args.get('formato', 'pdf')
        
        subquery_deben = db.session.query(Pago.id_alumno).filter(Pago.estado == 'PENDIENTE').subquery()
        query = Alumno.query.filter(Alumno.id_generacion == id_gen, ~Alumno.id_alumno.in_(subquery_deben)).order_by(Alumno.apellido, Alumno.nombre)
        if id_grupo and id_grupo not in ["", "null", "undefined"]: query = query.join(Grupo).filter(Grupo.nombre_grupo == id_grupo)
        
        alumnos = query.all()
        data = [{"Matrícula": a.matricula, "Alumno": f"{a.apellido} {a.nombre}".upper(), "Estatus": "AL CORRIENTE"} for a in alumnos]
        if formato == 'excel': return generar_excel(data, "Al Corriente", "Alumnos_Al_Corriente.xlsx")
        return generar_pdf_generico_pro("Listado de Alumnos al Corriente", data, colors.HexColor("#0891b2"), "Al_Corriente.pdf")
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Error interno"}), 500