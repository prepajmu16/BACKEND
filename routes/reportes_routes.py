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

# --- [LAS FUNCIONES DE GENERACIÓN PDF Y EXCEL SE QUEDAN EXACTAMENTE IGUAL] ---
# Omití reescribir pie_de_pagina, crear_encabezado_logo, generar_pdf_deudores_pro, 
# generar_pdf_generico_pro y generar_excel para ahorrar espacio, 
# ¡tus funciones de diseño están perfectas y no necesitan cambios!
# ------------------------------------------------------------------------------

# ==========================================
#                ENDPOINTS
# ==========================================

@reportes_bp.route("/reportes/dashboard", methods=["GET", "OPTIONS"])
def dashboard_ingresos():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        hoy = date.today(); p_mes = hoy.replace(day=1)
        
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
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "Solo administradores pueden descargar el corte de caja"}), 403

    try:
        formato = request.args.get('formato', 'pdf'); hoy = date.today()
        pagos = db.session.query(Pago, Alumno, EstructuraPago).select_from(Pago).join(Alumno).join(EstructuraPago).filter(Pago.fecha_pago == hoy).all()
        
        def formato_folio(p):
            folio_str = str(p.folio or "S/F")
            if getattr(p, 'estado', '') == 'PARCIAL': return folio_str
            return folio_str.split('(')[0].strip()

        data = []
        total_suma = 0 
        for p, a, e in pagos:
            monto_real = float(p.monto_abonado) if p.monto_abonado else float(e.monto or 0)
            if getattr(p, 'estado', '') == 'PAGADO' or monto_real > 0:
                total_suma += monto_real
                data.append({
                    "Folio": formato_folio(p), 
                    "Alumno": f"{a.apellido} {a.nombre}".upper(), 
                    "Concepto": e.concepto, 
                    "Monto": "${:,.2f}".format(monto_real)
                })
        
        try: registrar_accion(operador.get('id'), "DESCARGA_CORTE_CAJA", f"Descargó el Corte de Caja del día de hoy en formato {formato.upper()}")
        except: pass

        if formato == 'excel': 
            if data: data.append({"Folio": "", "Alumno": "", "Concepto": "TOTAL DEL DÍA", "Monto": "${:,.2f}".format(total_suma)})
            return generar_excel(data, "Corte", f"Corte_{hoy}.xlsx")
            
        return generar_pdf_generico_pro(f"CORTE DE CAJA DIARIO", data, colors.HexColor("#1E293B"), "Corte.pdf", total_suma=total_suma, titulo_total="TOTAL INGRESOS DEL DÍA")
    except Exception as e: return jsonify({"error": str(e)}), 500

@reportes_bp.route("/reportes/ingresos", methods=["GET", "OPTIONS"])
def reporte_ingresos():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
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
            if getattr(p, 'estado', '') == 'PAGADO' or monto_real > 0:
                total_suma += monto_real
                data.append({
                    "Fecha": p.fecha_pago.strftime("%d/%m/%Y"), 
                    "Alumno": f"{a.apellido} {a.nombre}".upper(), 
                    "Concepto": e.concepto, 
                    "Monto": "${:,.2f}".format(monto_real)
                })
        
        if formato == 'excel': 
            if data: data.append({"Fecha": "", "Alumno": "", "Concepto": "TOTAL INGRESOS", "Monto": "${:,.2f}".format(total_suma)})
            return generar_excel(data, "Ingresos", "Historico_Ingresos.xlsx")
            
        return generar_pdf_generico_pro(f"HISTÓRICO DE INGRESOS ({inicio} al {fin})", data, colors.HexColor("#1E293B"), "Historico.pdf", total_suma=total_suma, titulo_total="TOTAL GENERAL DE INGRESOS")
    except Exception as e: return jsonify({"error": str(e)}), 500

@reportes_bp.route("/reportes/deudores", methods=["GET", "OPTIONS"])
def reporte_deudores():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
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
        
        for a in alumnos:
            f_limite = a.fecha_baja if (a.estatus == 'BAJA' and a.fecha_baja) else date.today()
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
        if not data: return jsonify({"error": "Sin deudores"}), 404
        
        if formato == 'excel':
            return generar_excel([{"Matrícula": x["Matrícula"], "Alumno": x["Alumno"], "Adeudo": x["Total"]} for x in data], "Deudores", "Deudores.xlsx")
            
        titulo = f"ALUMNOS CON DEUDAS" + (f" - {sem}° SEM" if sem else "")
        return generar_pdf_deudores_pro(data, titulo, "Deudores.pdf")
    except Exception as e: return jsonify({"error": str(e)}), 500

@reportes_bp.route("/reportes/al-corriente", methods=["GET", "OPTIONS"])
def reporte_al_corriente():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    id_gen = limpiar_param(request.args.get('generacion'))
    try:
        id_grupo = limpiar_param(request.args.get('grupo')); sem = limpiar_param(request.args.get('semestre')); formato = request.args.get('formato', 'pdf')
        
        try: registrar_accion(operador.get('id'), "DESCARGA_AL_CORRIENTE", f"Descargó reporte de alumnos al corriente (Gen: {id_gen}, Grupo: {id_grupo or 'Todos'}, Sem: {sem or 'Todos'}) en formato {formato.upper()}")
        except: pass

        query = Alumno.query.filter(Alumno.id_generacion == int(id_gen), Alumno.estatus == 'ACTIVO')
        if id_grupo: query = query.join(Grupo).filter(Grupo.nombre_grupo == id_grupo)
        if sem: query = query.filter(Alumno.semestre_actual == int(sem))
        
        alumnos = query.all(); data = []
        for a in alumnos:
            tiene_deuda = False
            pagos = db.session.query(Pago, EstructuraPago).join(EstructuraPago).filter(Pago.id_alumno == a.id_alumno, Pago.estado != 'PAGADO').all()
            for p, e in pagos:
                if (e.semestre or 1) <= (a.semestre_actual or 1):
                    if e.anio and e.mes:
                        if e.anio < date.today().year or (e.anio == date.today().year and e.mes <= date.today().month): tiene_deuda = True; break
                    else: tiene_deuda = True; break
            if not tiene_deuda:
                data.append({"Matrícula": a.matricula, "Alumno": f"{a.apellido} {a.nombre}".upper(), "Estatus": "AL CORRIENTE"})
                
        if not data: return jsonify({"error": "Sin alumnos al corriente"}), 404
        
        titulo = f"ALUMNOS AL CORRIENTE" + (f" - {sem}° SEM" if sem else "")
        if formato == 'excel': return generar_excel(data, "Al Corriente", "Alumnos_Al_Corriente.xlsx")
        return generar_pdf_generico_pro(titulo, data, colors.HexColor("#1E293B"), "Al_Corriente.pdf")
    except Exception as e: return jsonify({"error": str(e)}), 500

@reportes_bp.route("/reportes/respaldo", methods=["GET", "OPTIONS"])
def respaldo_db():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL MÁXIMO (SOLO SISTEMAS)
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
        
        fecha_str = datetime.now().strftime("%d_%m_%Y_%H%M")
        nombre_archivo = f"Respaldo_Prepa_{fecha_str}.sql"

        try: registrar_accion(operador.get('id'), "RESPALDO_BD", "Descargó un respaldo técnico completo (.sql) de la base de datos.")
        except: pass

        return send_file(buffer, as_attachment=True, download_name=nombre_archivo, mimetype='application/sql')

    except Exception as e: 
        return jsonify({"error": str(e)}), 500

