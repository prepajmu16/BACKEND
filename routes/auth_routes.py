from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import Usuario

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    identificador = data.get("correo") 
    contraseña_entrada = data.get("password")

    usuario = Usuario.query.filter_by(correo=identificador).first()
    if usuario and check_password_hash(usuario.contraseña, contraseña_entrada):
        access_token = create_access_token(identity={"id": usuario.id_usuario, "rol": usuario.rol, "nombre": usuario.nombre})
        return jsonify({"message": "Bienvenido", "token": access_token, "rol": usuario.rol, "usuario": usuario.nombre, "correo": usuario.correo}), 200
    return jsonify({"message": "Usuario/Matrícula o contraseña incorrectos"}), 401

@auth_bp.route("/perfil", methods=["GET"])
@jwt_required()
def perfil():
    return jsonify(get_jwt_identity()), 200

@auth_bp.route('/actualizar_password', methods=['POST', 'OPTIONS'])
def actualizar_password():
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        data = request.get_json()
        usuario = Usuario.query.filter_by(correo=data.get('correoUsuario')).first()
        if not usuario: return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        if not check_password_hash(usuario.contraseña, data.get('passActual')): return jsonify({"status": "error", "mensaje": "Contraseña actual incorrecta"}), 401
        
        usuario.contraseña = generate_password_hash(data.get('passNueva'))
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Contraseña actualizada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error en servidor"}), 500 

@auth_bp.route('/actualizar_perfil', methods=['PUT', 'OPTIONS'])
def actualizar_perfil():
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        data = request.get_json()
        usuario = Usuario.query.filter_by(correo=data.get('correoActual')).first()
        if not usuario: return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        
        nuevo_correo = data.get('correo')
        if nuevo_correo != data.get('correoActual') and Usuario.query.filter_by(correo=nuevo_correo).first():
            return jsonify({"status": "error", "mensaje": "El correo ya está en uso"}), 400

        usuario.nombre, usuario.correo = data.get('nombre'), nuevo_correo
        if hasattr(usuario, 'puesto') and data.get('puesto'): usuario.puesto = data.get('puesto')
        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Perfil actualizado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error en servidor"}), 500