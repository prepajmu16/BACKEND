from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta

# ✅ IMPORTACIONES ACTUALIZADAS: Agregamos Alumno, EstructuraPago, Pago
from modelos import db, Generacion, Usuario, Bitacora, Alumno, EstructuraPago, Pago
from config import config

app = Flask(__name__)

# ==========================
# 🔐 CONFIGURACIÓN DE SEGURIDAD
# ==========================
app.config["JWT_SECRET_KEY"] = "super-clave-secreta-residencia-2025" 
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2) 

jwt = JWTManager(app)

# ==========================
# CONFIGURACIÓN APP Y BD
# ==========================
CORS(app, origins=["http://localhost:4200"])
app.config.from_object(config['development'])
db.init_app(app)

# ==========================
# RUTAS GENERALES
# ==========================
@app.route("/")
def home():
    return jsonify({"message": "API Sistema Prepa activa 🚀"})

# ==========================
# MÓDULO DE AUTENTICACIÓN (LOGIN)
# ==========================
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    
    # Recibimos el identificador (Puede ser Correo Admin O Matrícula Alumno)
    identificador = data.get("correo") 
    contraseña_entrada = data.get("password")

    # 1. Buscamos al usuario 
    # (Como decidimos que para alumnos el 'correo' guardará la matrícula, 
    # esta búsqueda funciona para ambos casos sin cambiar nada).
    usuario = Usuario.query.filter_by(correo=identificador).first()

    # 2. Verificamos contraseña encriptada
    if usuario and check_password_hash(usuario.contraseña, contraseña_entrada):
        
        # 3. Creamos el token
        access_token = create_access_token(identity={
            "id": usuario.id_usuario,
            "rol": usuario.rol,
            "nombre": usuario.nombre
        })

        return jsonify({
            "message": "Bienvenido",
            "token": access_token,
            "rol": usuario.rol,
            "usuario": usuario.nombre
        }), 200

    return jsonify({"message": "Usuario/Matrícula o contraseña incorrectos"}), 401


@app.route("/perfil", methods=["GET"])
@jwt_required()
def perfil():
    current_user = get_jwt_identity()
    return jsonify(current_user), 200

# ==========================
# MÓDULO DE USUARIOS (Administrativos)
# ==========================
@app.route("/usuarios", methods=["POST"])
def registrar_usuario():
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    if not all(k in data for k in ("nombre", "correo", "contraseña", "rol")):
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    usuario_existente = Usuario.query.filter_by(correo=data["correo"]).first()
    if usuario_existente:
        return jsonify({"error": "El correo ya está registrado"}), 400

    password_hash = generate_password_hash(data["contraseña"])

    # Lógica de Puesto (Solo para ADMIN)
    puesto_asignado = data.get("puesto") if data["rol"] == 'ADMIN' else None

    nuevo_usuario = Usuario(
        nombre=data["nombre"],
        correo=data["correo"],
        contraseña=password_hash,
        rol=data["rol"],
        puesto=puesto_asignado,
        estado="ACTIVO"
    )

    try:
        db.session.add(nuevo_usuario)
        db.session.commit()

        # Registro en Bitácora (Temporal id=1)
        nueva_accion = Bitacora(
            id_usuario=1, 
            accion="REGISTRO_USUARIO",
            descripcion=f"Se registró usuario {nuevo_usuario.correo} ({nuevo_usuario.rol}) - Cargo: {puesto_asignado}"
        )
        db.session.add(nueva_accion)
        db.session.commit()

        return jsonify({
            "message": "Usuario registrado correctamente",
            "usuario": nuevo_usuario.correo
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# ✅ NUEVO: MÓDULO DE ALUMNOS (Inscripción)
# ==========================
@app.route("/alumnos", methods=["POST"])
def registrar_alumno():
    data = request.get_json()

    # Validamos datos (matricula es vital)
    if not all(k in data for k in ("matricula", "nombre", "apellido", "id_generacion")):
        return jsonify({"error": "Faltan datos (matricula, nombre, apellido, id_generacion)"}), 400

    # Validar duplicados
    if Alumno.query.filter_by(matricula=data["matricula"]).first():
        return jsonify({"error": "La matrícula ya existe"}), 400

    try:
        # 1. CREAR USUARIO (Login)
        # Usuario = Matrícula | Contraseña = Matrícula
        nuevo_usuario = Usuario(
            nombre=f"{data['nombre']} {data['apellido']}",
            correo=data["matricula"], # Guardamos la matrícula en el campo correo
            contraseña=generate_password_hash(data["matricula"]), # Pass inicial = Matrícula
            rol='ALUMNO',
            estado='ACTIVO'
        )
        db.session.add(nuevo_usuario)
        db.session.flush() 

        # 2. CREAR ALUMNO (Perfil)
        nuevo_alumno = Alumno(
            matricula=data["matricula"],
            nombre=data["nombre"],
            apellido=data["apellido"],
            id_generacion=data["id_generacion"],
            id_usuario=nuevo_usuario.id_usuario,
            estatus='ACTIVO'
        )
        db.session.add(nuevo_alumno)
        db.session.flush()

        # 3. GENERAR ADEUDOS (Automático)
        conceptos = EstructuraPago.query.filter_by(id_generacion=data["id_generacion"]).all()
        
        pagos_creados = 0
        for c in conceptos:
            pago = Pago(
                id_alumno=nuevo_alumno.id_alumno,
                id_estructura=c.id_estructura,
                monto_pagado=0,
                estado='PENDIENTE',
                numero_oportunidad=1
            )
            db.session.add(pago)
            pagos_creados += 1

        db.session.commit()

        return jsonify({
            "message": "Alumno inscrito correctamente",
            "usuario": data["matricula"],
            "pagos_generados": pagos_creados
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# MÓDULO DE GENERACIONES
# ==========================
@app.route("/generaciones", methods=["POST"])
def registrar_generacion():
    data = request.get_json()
    # ... (Tu código de generaciones está bien)
    nueva_gen = Generacion(
        nombre=data["nombre"],
        fecha_inicio=data["fecha_inicio"],
        fecha_fin=data["fecha_fin"]
    )
    db.session.add(nueva_gen)
    db.session.commit()
    return jsonify({"message": "Generación creada"}), 201

@app.route("/generaciones", methods=["GET"])
def listar_generaciones():
    generaciones = Generacion.query.all()
    resultado = []
    for g in generaciones:
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": g.fecha_inicio.strftime("%Y-%m-%d"),
            "fecha_fin": g.fecha_fin.strftime("%Y-%m-%d"),
            "estado": g.estado
        })
    return jsonify(resultado), 200

# ==========================
# INICIO DE LA APP
# ==========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)