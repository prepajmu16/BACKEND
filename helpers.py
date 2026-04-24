from extensions import db
from models.bitacora import Bitacora
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask import request 
from datetime import datetime
from zoneinfo import ZoneInfo
import traceback # 🔥 El chismoso que nos dirá si SQL falla

def obtener_id_admin():
    """Extrae el ID del usuario desde el Token JWT de forma segura"""
    try:
        verify_jwt_in_request(optional=True)
        identidad = get_jwt_identity()
        
        if isinstance(identidad, dict):
            return identidad.get('id')
        elif identidad is not None:
            return int(identidad)
            
        return None 
    except:
        return None

def registrar_accion(id_usuario, accion, descripcion):
    """Guarda en bitácora con hora plana para que MySQL no explote"""
    try:
        ip_cliente = request.remote_addr if request else "127.0.0.1"

        # 🕒 1. Calculamos la hora exacta de México
        hora_con_zona = datetime.now(ZoneInfo("America/Mexico_City"))
        
        # 🕒 2. Le quitamos la etiqueta de país (Naive Datetime) para que MySQL la acepte
        hora_plana = hora_con_zona.replace(tzinfo=None)

        # 🛡️ 3. Protección de usuario (Asegúrate de que el ID 1 exista en tu tabla Usuario)
        if not id_usuario:
            from models.usuario import Usuario
            primer_usuario = Usuario.query.first()
            id_usuario = primer_usuario.id_usuario if primer_usuario else 1

        nuevo_log = Bitacora(
            id_usuario=id_usuario, 
            accion=accion,
            descripcion=descripcion,
            ip=ip_cliente,
            fecha=hora_plana # 🔥 Mandamos la fecha plana y corregida
        )
        db.session.add(nuevo_log)
        db.session.commit()
        print(f"✅ BITÁCORA OK: {accion} a las {hora_plana.strftime('%H:%M:%S')}")
        
    except Exception as e:
        db.session.rollback()
        print(f"\n⚠️ --- ERROR FATAL AL GUARDAR EN BITÁCORA ---")
        traceback.print_exc() # Esto imprimirá el error real de la base de datos
        print("--------------------------------------------\n")
        
""" from extensions import db
from models.bitacora import Bitacora
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def obtener_id_admin():
    try:
        verify_jwt_in_request(optional=True)
        identidad = get_jwt_identity()
        if isinstance(identidad, dict):
            return identidad.get('id', 1)
        return 1
    except:
        return 1

def registrar_accion(id_usuario, accion, descripcion):
    try:
        nuevo_log = Bitacora(
            id_usuario=id_usuario,
            accion=accion,
            descripcion=descripcion
        )
        db.session.add(nuevo_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error guardando en bitácora: {e}") """