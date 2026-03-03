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

# ✅ IMPORTACIONES COMPLETAS
from modelos import db, Generacion, Usuario, Bitacora, Alumno, EstructuraPago, Pago, Grupo
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
# MÓDULO DE ALUMNOS (Inscripción)
# ==========================
@app.route("/alumnos", methods=["POST"])
def registrar_alumno():
    data = request.get_json()

    if not all(k in data for k in ("matricula", "nombre", "apellido", "id_generacion")):
        return jsonify({"error": "Faltan datos (matricula, nombre, apellido, id_generacion)"}), 400

    if Alumno.query.filter_by(matricula=data["matricula"]).first():
        return jsonify({"error": "La matrícula ya existe"}), 400

    try:
        # 1. CREAR USUARIO (Login)
        nuevo_usuario = Usuario(
            nombre=f"{data['nombre']} {data['apellido']}",
            correo=data["matricula"],
            contraseña=generate_password_hash(data["matricula"]),
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

        # 3. GENERAR ADEUDOS
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
# ✅ MÓDULO DE GENERACIONES (Actualizado para el ERP)
# ==========================
@app.route("/generaciones", methods=["POST"])
def registrar_generacion():
    data = request.get_json()
    
    try:
        nueva_gen = Generacion(
            nombre=data["nombre"],
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            estado=data.get("estado", "ACTIVA")
        )
        db.session.add(nueva_gen)
        db.session.commit()
        return jsonify({"message": "Generación creada"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/generaciones", methods=["GET"])
def listar_generaciones():
    generaciones = Generacion.query.all()
    resultado = []
    
    for g in generaciones:
        # ✅ Magia de SQL y Python: Contamos activos y bajas leyendo la relación g.alumnos
        activos = sum(1 for a in g.alumnos if a.estatus == 'ACTIVO')
        bajas = sum(1 for a in g.alumnos if a.estatus in ['BAJA', 'SUSPENDIDO'])
        
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": g.fecha_inicio.strftime("%Y-%m-%d"),
            "fecha_fin": g.fecha_fin.strftime("%Y-%m-%d"),
            "estado": g.estado,
            "activos": activos,  # Enviamos los contadores a Angular
            "bajas": bajas
        })
    return jsonify(resultado), 200

# ✅ NUEVO: Ruta PUT para editar y cambiar estado ("Apagar" Generación)
@app.route("/generaciones/<int:id_generacion>", methods=["PUT"])
def actualizar_generacion(id_generacion):
    data = request.get_json()
    
    generacion = Generacion.query.get(id_generacion)
    if not generacion:
        return jsonify({"error": "Generación no encontrada"}), 404

    try:
        # Actualizamos solo los datos que vengan en el request
        if "nombre" in data:
            generacion.nombre = data["nombre"]
        if "fecha_inicio" in data:
            generacion.fecha_inicio = data["fecha_inicio"]
        if "fecha_fin" in data:
            generacion.fecha_fin = data["fecha_fin"]
        if "estado" in data:
            generacion.estado = data["estado"]

        db.session.commit()
        return jsonify({"message": "Generación actualizada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================
# MÓDULO DASHBOARD
# ==========================
@app.route('/api/dashboard/admin', methods=['GET'])
def obtener_datos_dashboard():
    alumnos = Alumno.query.all()
    generaciones = Generacion.query.all()
    grupos = Grupo.query.all()

    return jsonify({
        "alumnos": [a.to_dict() for a in alumnos], 
        "generaciones": [{"id": g.id_generacion, "nombre": g.nombre} for g in generaciones],
        "grupos": [{"id": gr.id_grupo, "nombre": gr.nombre_grupo} for gr in grupos]
    })   

# ==========================
# MÓDULO DE GRUPOS
# ==========================
@app.route("/grupos", methods=["POST"])
def registrar_grupo():
    data = request.get_json()
    
    try:
        # 🛡️ VALIDACIÓN: ¿Ya existe el mismo nombre en la misma generación?
        id_gen = int(data["id_generacion"])
        nombre = data["nombre_grupo"].upper() # Lo pasamos a mayúsculas para evitar 'a' vs 'A'

        existe = Grupo.query.filter_by(nombre_grupo=nombre, id_generacion=id_gen).first()
        
        if existe:
            return jsonify({
                "error": f"El Grupo {nombre} ya está registrado para esta generación."
            }), 400

        nuevo_grupo = Grupo(
            nombre_grupo=nombre,
            turno=data.get("turno", "Vespertino"), # Forzamos Vespertino por defecto
            id_generacion=id_gen
        )
        db.session.add(nuevo_grupo)
        db.session.commit()
        return jsonify({"message": "Grupo creado exitosamente"}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/grupos", methods=["GET"])
def listar_grupos():
    grupos = Grupo.query.all()
    resultado = []
    
    for g in grupos:
        activos = sum(1 for a in g.alumnos if a.estatus == 'ACTIVO')
        resultado.append({
            "id_grupo": g.id_grupo,
            "nombre_grupo": g.nombre_grupo,
            "turno": g.turno,
            "id_generacion": g.id_generacion,
            "nombre_gen": g.generacion.nombre if g.generacion else "Sin Generación",
            "total_alumnos": activos
        })
    return jsonify(resultado), 200

@app.route("/grupos/<int:id_grupo>", methods=["PUT"])
def actualizar_grupo(id_grupo):
    data = request.get_json()
    grupo = Grupo.query.get(id_grupo)
    
    if not grupo:
        return jsonify({"error": "Grupo no encontrado"}), 404
    
    try:
        # 🛡️ VALIDACIÓN EN EDICIÓN: Evitar duplicados al renombrar
        nuevo_nombre = data.get("nombre_grupo", grupo.nombre_grupo).upper()
        nueva_gen = int(data.get("id_generacion", grupo.id_generacion))

        # Buscamos si hay OTRO grupo (diferente al actual) que ya tenga esos datos
        existe = Grupo.query.filter(
            Grupo.id_grupo != id_grupo, 
            Grupo.nombre_grupo == nuevo_nombre, 
            Grupo.id_generacion == nueva_gen
        ).first()

        if existe:
            return jsonify({
                "error": f"No puedes actualizar: El Grupo {nuevo_nombre} ya existe en esa generación."
            }), 400

        grupo.nombre_grupo = nuevo_nombre
        grupo.turno = data.get("turno", grupo.turno)
        grupo.id_generacion = nueva_gen
            
        db.session.commit()
        return jsonify({"message": "Grupo actualizado correctamente"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# ==========================
# INICIO DE LA APP
# ==========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)