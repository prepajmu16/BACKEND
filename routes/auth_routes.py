from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt, get_jwt_identity, verify_jwt_in_request
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import Usuario
from helpers import registrar_accion

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    identificador = data.get("correo") 
    contraseña_entrada = data.get("password")

    usuario = Usuario.query.filter_by(correo=identificador).first()
    
    if usuario and check_password_hash(usuario.contraseña, contraseña_entrada):
        
        # 🔥 CORRECCIÓN DEL TOKEN: identity es un String, los datos van en additional_claims
        access_token = create_access_token(
            identity=str(usuario.id_usuario), 
            additional_claims={
                "id": usuario.id_usuario, 
                "rol": usuario.rol, 
                "nombre": usuario.nombre
            }
        )
        
        # 📸 BITÁCORA: Registro de inicio de sesión
        registrar_accion(
            id_usuario=usuario.id_usuario,
            accion="LOGIN",
            descripcion=f"El usuario {usuario.nombre} ({usuario.correo}) inició sesión en el sistema."
        )

        return jsonify({
            "message": "Bienvenido", 
            "token": access_token, 
            "rol": usuario.rol, 
            "usuario": usuario.nombre, 
            "correo": usuario.correo
        }), 200
        
    return jsonify({"message": "Usuario/Matrícula o contraseña incorrectos"}), 401

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        current_user_id = get_jwt_identity()
        claims = get_jwt()
        nombre_usuario = claims.get('nombre', 'Usuario Desconocido')

        # 📸 BITÁCORA
        registrar_accion(
            id_usuario=current_user_id,
            accion="LOGOUT",
            descripcion=f"El usuario {nombre_usuario} cerró sesión en el sistema."
        )

        return jsonify({"message": "Sesión cerrada correctamente"}), 200

    except Exception as e:
        print(f"🔥 ERROR EN BACKEND LOGOUT: {e}") # Esto saldrá en la pantallita negra de tu servidor Flask
        return jsonify({"error": str(e)}), 500
@auth_bp.route("/perfil", methods=["GET"])
@jwt_required()
def perfil():
    # Usamos get_jwt() para extraer los additional_claims
    return jsonify(get_jwt()), 200


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

        # 📸 BITÁCORA: Actualización de contraseña propia
        registrar_accion(
            id_usuario=usuario.id_usuario,
            accion="ACTUALIZAR_PASSWORD",
            descripcion=f"El usuario {usuario.correo} actualizó su propia contraseña desde el perfil."
        )

        return jsonify({"status": "success", "mensaje": "Contraseña actualizada"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error en servidor"}), 500 


@auth_bp.route('/actualizar_perfil', methods=['PUT', 'OPTIONS'])
def actualizar_perfil():
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        data = request.get_json()
        correo_original = data.get('correoActual')
        usuario = Usuario.query.filter_by(correo=correo_original).first()
        
        if not usuario: return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        
        nuevo_correo = data.get('correo')
        if nuevo_correo != correo_original and Usuario.query.filter_by(correo=nuevo_correo).first():
            return jsonify({"status": "error", "mensaje": "El correo ya está en uso"}), 400

        usuario.nombre = data.get('nombre')
        usuario.correo = nuevo_correo
        if hasattr(usuario, 'puesto') and data.get('puesto'): usuario.puesto = data.get('puesto')
        
        db.session.commit()

        # 📸 BITÁCORA: Edición de perfil
        registrar_accion(
            id_usuario=usuario.id_usuario,
            accion="ACTUALIZAR_PERFIL",
            descripcion=f"El usuario {correo_original} actualizó su información. Nuevo correo: {usuario.correo}, Nombre: {usuario.nombre}."
        )

        return jsonify({"status": "success", "mensaje": "Perfil actualizado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error en servidor"}), 500