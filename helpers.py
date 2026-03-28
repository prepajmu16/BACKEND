from extensions import db
from models.bitacora import Bitacora
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity

def obtener_id_admin():
    """Extrae el ID del usuario desde el Token JWT de forma segura"""
    try:
        verify_jwt_in_request(optional=True)
        identidad = get_jwt_identity()
        if isinstance(identidad, dict):
            return identidad.get('id', 1)
        return 1
    except:
        return 1

def registrar_accion(id_usuario, accion, descripcion):
    """Guarda automáticamente un movimiento en la tabla bitacora"""
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
        print(f"⚠️ Error guardando en bitácora: {e}")