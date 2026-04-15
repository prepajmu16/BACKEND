from extensions import db
from models.bitacora import Bitacora
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from flask import request # 🔥 IMPORTANTE: Importamos request para leer la IP

def obtener_id_admin():
    """Extrae el ID del usuario desde el Token JWT de forma segura"""
    try:
        verify_jwt_in_request(optional=True)
        identidad = get_jwt_identity()
        
        # Dependiendo de cómo guardaste el token, puede ser un dict o un string
        if isinstance(identidad, dict):
            return identidad.get('id')
        elif identidad is not None:
            return int(identidad)
            
        return None # 🔥 Mejor retornar None para saber que fue un error/sistema
    except:
        return None

def registrar_accion(id_usuario, accion, descripcion):
    """Guarda automáticamente un movimiento en la tabla bitacora"""
    try:
        # 🔥 Detectamos la IP real desde donde hicieron el clic
        ip_cliente = request.remote_addr if request else "127.0.0.1"

        nuevo_log = Bitacora(
            # Si no hay usuario (ej. un error del sistema), lo asignamos al 1 por defecto 
            # (o puedes cambiar tu BD para aceptar nulos en id_usuario)
            id_usuario=id_usuario or 1, 
            accion=accion,
            descripcion=descripcion,
            ip=ip_cliente # 🔥 Guardamos la IP en la base de datos
        )
        db.session.add(nuevo_log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"⚠️ Error guardando en bitácora: {e}")

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