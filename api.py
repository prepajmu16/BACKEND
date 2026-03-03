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
# MÓDULO DE ALUMNOS (Inscripción y Listado)
# ==========================

@app.route("/alumnos", methods=["GET"])
def listar_alumnos():
    try:
        # Usamos outerjoin para traer al alumno aunque no tenga grupo asignado (como Carlos)
        alumnos = Alumno.query.all()
        # El to_dict() que definiste en modelos.py se encarga de los nombres de gen y grupo
        return jsonify([a.to_dict() for a in alumnos]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/alumnos", methods=["POST"])
def registrar_alumno():
    data = request.get_json()

    # Validación básica
    campos = ("matricula", "nombre", "apellido", "id_generacion", "id_grupo")
    if not all(k in data for k in campos):
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    if Alumno.query.filter_by(matricula=data["matricula"]).first():
        return jsonify({"error": "La matrícula ya existe"}), 400

    try:
        # 1. Crear Usuario para el portal
        nuevo_usuario = Usuario(
            nombre=f"{data['nombre']} {data['apellido']}",
            correo=data["matricula"],
            contraseña=generate_password_hash(data["matricula"]),
            rol='ALUMNO'
        )
        db.session.add(nuevo_usuario)
        db.session.flush() 

        # 2. Crear Alumno con el Semestre 1 por defecto
        nuevo_alumno = Alumno(
            matricula=data["matricula"],
            nombre=data["nombre"],
            apellido=data["apellido"],
            id_generacion=data["id_generacion"],
            id_grupo=data["id_grupo"], # Ya permite el ID de los grupos A o B que creamos
            id_usuario=nuevo_usuario.id_usuario,
            semestre_actual=1, # ✅ Aseguramos que entre a 1ro para que Angular lo vea
            estatus='ACTIVO'
        )
        db.session.add(nuevo_alumno)
        db.session.flush()

        # 3. Generar Adeudos automáticos
        conceptos = EstructuraPago.query.filter_by(id_generacion=data["id_generacion"]).all()
        for c in conceptos:
            pago = Pago(
                id_alumno=nuevo_alumno.id_alumno,
                id_estructura=c.id_estructura,
                estado='PENDIENTE',
                numero_oportunidad=1
            )
            db.session.add(pago)

        db.session.commit()
        return jsonify({"message": "Inscripción exitosa", "usuario": data["matricula"]}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@app.route("/alumnos/<string:matricula>", methods=["PUT"])
def actualizar_estatus_alumno(matricula):
    data = request.get_json()
    alumno = Alumno.query.filter_by(matricula=matricula).first()

    if not alumno:
        return jsonify({"error": "Alumno no encontrado"}), 404

    try:
        # Actualizamos solo lo que venga en el JSON
        if "estatus" in data:
            alumno.estatus = data["estatus"]
        if "semestre_actual" in data:
            alumno.semestre_actual = int(data["semestre_actual"])
        if "id_grupo" in data:
            alumno.id_grupo = data["id_grupo"]

        db.session.commit()

        # Opcional: Registrar el movimiento en bitácora
        nueva_bitacora = Bitacora(
            id_usuario=1, 
            accion="ACTUALIZAR_TRAYECTORIA",
            descripcion=f"Alumno {matricula} movido a {alumno.estatus} en Semestre {alumno.semestre_actual}"
        )
        db.session.add(nueva_bitacora)
        db.session.commit()

        return jsonify({"message": "Trayectoria actualizada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500  
    
# ✅ Asegúrate de incluir methods=["POST"]
@app.route("/alumnos/promocion-masiva", methods=["POST"])
def promocion_masiva():
    data = request.get_json()
    id_gen = data.get("id_generacion")
    
    if not id_gen:
        return jsonify({"error": "Debes especificar la generación"}), 400

    try:
        # 1. Los que están en 6to semestre pasan a ser 'EGRESADO'
        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen,
            Alumno.semestre_actual == 6,
            Alumno.estatus == 'ACTIVO'
        ).update({Alumno.estatus: 'EGRESADO'}, synchronize_session=False)

        # 2. Los que están entre 1ro y 5to suben un nivel
        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen,
            Alumno.semestre_actual < 6,
            Alumno.estatus == 'ACTIVO'
        ).update({Alumno.semestre_actual: Alumno.semestre_actual + 1}, synchronize_session=False)

        db.session.commit()
        return jsonify({"message": "Promoción completada exitosamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 
# ==========================
# PROMOCIÓN SELECTIVA
# ==========================
@app.route("/alumnos/promocion-selectiva", methods=["POST"])
def promocion_selectiva():
    data = request.get_json()
    ids_alumnos = data.get("ids_alumnos", [])
    # ✅ Ahora recibimos el semestre al que quieres enviarlos
    semestre_destino = data.get("semestre_destino")
    
    if not ids_alumnos or not semestre_destino:
        return jsonify({"error": "Faltan alumnos o semestre de destino"}), 400

    try:
        # 1. Si el destino es 7 o más, los graduamos
        if int(semestre_destino) > 6:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.estatus: 'EGRESADO', Alumno.semestre_actual: 6}, synchronize_session=False)
        else:
            # 2. Los movemos al semestre exacto que seleccionó la secretaria
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.semestre_actual: int(semestre_destino)}, synchronize_session=False)

        db.session.commit()
        return jsonify({"message": f"Promoción a {semestre_destino}° exitosa"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
# ==========================================
# 🗑️ ELIMINAR ALUMNO (CON LIMPIEZA DE DATOS)
# ==========================================
@app.route("/alumnos/<string:matricula>", methods=["DELETE"])
def eliminar_alumno(matricula):
    alumno = Alumno.query.filter_by(matricula=matricula).first()
    
    if not alumno:
        return jsonify({"error": "El alumno no existe"}), 404

    try:
        # 1. Eliminar registros de pagos vinculados (para evitar errores de FK)
        Pago.query.filter_by(id_alumno=alumno.id_alumno).delete()
        
        # 2. Identificar al usuario vinculado
        id_usuario_vinculado = alumno.id_usuario
        
        # 3. Eliminar al alumno
        db.session.delete(alumno)
        db.session.flush() # Sincroniza sin confirmar todavía
        
        # 4. Eliminar el usuario del portal (opcional, pero recomendado)
        if id_usuario_vinculado:
            Usuario.query.filter_by(id_usuario=id_usuario_vinculado).delete()

        db.session.commit()
        return jsonify({"message": f"Alumno {matricula} y sus datos relacionados han sido eliminados"}), 200

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