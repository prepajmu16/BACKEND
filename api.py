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
            "usuario": usuario.nombre,
            "correo": usuario.correo
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
        alumnos = Alumno.query.all()
        resultado = []
        for a in alumnos:
            nombre_gen = a.generacion.nombre if a.generacion else "Sin Generación"
            nombre_grupo = a.grupo.nombre_grupo if a.grupo else "Sin Grupo"
            
            resultado.append({
                "id_alumno": a.id_alumno,
                "matricula": a.matricula,
                "nombre": a.nombre,          # ✅ AHORA ENVIAMOS EL NOMBRE SEPARADO
                "apellido": a.apellido,      # ✅ AHORA ENVIAMOS EL APELLIDO SEPARADO
                "nombre_completo": f"{a.nombre} {a.apellido}",
                "estatus": a.estatus,
                "semestre_actual": a.semestre_actual,
                "id_generacion": a.id_generacion,
                "nombre_generacion": nombre_gen,
                "id_grupo": a.id_grupo,
                "nombre_grupo": nombre_grupo
            })
        return jsonify(resultado), 200
    except Exception as e:
        print("🔴 ERROR EN GET /alumnos:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/alumnos", methods=["POST", "OPTIONS"])
def registrar_alumno():
    if request.method == "OPTIONS": return jsonify({}), 200
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
            id_grupo=data["id_grupo"], 
            id_usuario=nuevo_usuario.id_usuario,
            semestre_actual=1, 
            estatus='ACTIVO'
        )
        db.session.add(nuevo_alumno)
        db.session.flush()

        # 🛡️ 3. Generar Adeudos automáticos (SOLO SEMESTRE 1)
        conceptos = EstructuraPago.query.filter(
            EstructuraPago.id_generacion == data["id_generacion"],
            EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD']),
            EstructuraPago.semestre == 1  
        ).all()
        
        for c in conceptos:
            if c.concepto.upper().startswith('INSCRIP') or c.concepto.upper().startswith('MENS'):
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
        print("🔴 ERROR EN POST /alumnos:", str(e))
        return jsonify({"error": str(e)}), 500

# ==========================================
# ✏️ ACTUALIZAR ALUMNO (Con Auto-Generación de Deuda)
# ==========================================
@app.route("/alumnos/<string:matricula_original>", methods=["PUT", "OPTIONS"])
def actualizar_estatus_alumno(matricula_original):
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    
    # 1. Buscamos al alumno
    alumno = Alumno.query.filter_by(matricula=matricula_original).first()
    if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

    try:
        # 2. Si cambiaron la matrícula (con su respectiva validación)
        nueva_matricula = data.get("matricula")
        if nueva_matricula and nueva_matricula != matricula_original:
            existe = Alumno.query.filter_by(matricula=nueva_matricula).first()
            if existe: return jsonify({"error": "La nueva matrícula ya está en uso"}), 400
            
            if alumno.id_usuario:
                usuario = Usuario.query.get(alumno.id_usuario)
                if usuario: usuario.correo = nueva_matricula
            alumno.matricula = nueva_matricula

        # 3. Datos Personales y Estatus
        if "nombre" in data: alumno.nombre = data["nombre"]
        if "apellido" in data: alumno.apellido = data["apellido"]
        if "estatus" in data: alumno.estatus = data["estatus"]
        if "id_grupo" in data: alumno.id_grupo = data["id_grupo"]

        # 🔥 4. LA MAGIA: Si cambian el Semestre desde el Lapicito
        if "semestre_actual" in data:
            nuevo_semestre = int(data["semestre_actual"])
            
            # Verificamos si realmente lo movieron a un semestre distinto
            if nuevo_semestre != alumno.semestre_actual:
                alumno.semestre_actual = nuevo_semestre # Guardamos el nuevo número
                
                # Buscamos los cobros oficiales de ese nuevo semestre
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == nuevo_semestre,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).all()

                for c in conceptos:
                    # Candado: Evitamos duplicados por si ya se los habíamos generado antes
                    existe_pago = Pago.query.filter_by(id_alumno=alumno.id_alumno, id_estructura=c.id_estructura).first()
                    if not existe_pago:
                        db.session.add(Pago(
                            id_alumno=alumno.id_alumno,
                            id_estructura=c.id_estructura,
                            estado='PENDIENTE'
                        ))

        db.session.commit()
        return jsonify({"message": "Datos actualizados y cobros verificados"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
# ==========================
# 🚀 PROMOCIÓN MASIVA (Con Auto-Generación de Deuda)
# ==========================
@app.route("/alumnos/promocion-masiva", methods=["POST", "OPTIONS"])
def promocion_masiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    id_gen = data.get("id_generacion")
    
    if not id_gen: return jsonify({"error": "Debes especificar la generación"}), 400

    try:
        # 1. Los que están en 6to semestre pasan a 'EGRESADO'
        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual == 6, Alumno.estatus == 'ACTIVO'
        ).update({Alumno.estatus: 'EGRESADO'}, synchronize_session=False)

        # 2. Obtenemos a los alumnos que van a subir de semestre (1ro a 5to)
        alumnos_a_promover = Alumno.query.filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual < 6, Alumno.estatus == 'ACTIVO'
        ).all()

        for alumno in alumnos_a_promover:
            nuevo_semestre = alumno.semestre_actual + 1
            alumno.semestre_actual = nuevo_semestre # Le subimos el nivel

            # 🔥 3. MAGIA: Buscamos el paquete de cobros de su NUEVO semestre
            conceptos = EstructuraPago.query.filter(
                EstructuraPago.id_generacion == id_gen,
                EstructuraPago.semestre == nuevo_semestre,
                EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
            ).all()

            for c in conceptos:
                # Verificamos que no se lo hayamos cobrado antes (Evita duplicados si le das 2 veces al botón)
                existe = Pago.query.filter_by(id_alumno=alumno.id_alumno, id_estructura=c.id_estructura).first()
                if not existe:
                    db.session.add(Pago(
                        id_alumno=alumno.id_alumno,
                        id_estructura=c.id_estructura,
                        estado='PENDIENTE'
                    ))

        db.session.commit()
        return jsonify({"message": "Promoción completada y nuevos cobros generados"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 

# ==========================
# 🎯 PROMOCIÓN SELECTIVA (Con Auto-Generación de Deuda)
# ==========================
@app.route("/alumnos/promocion-selectiva", methods=["POST", "OPTIONS"])
def promocion_selectiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    ids_alumnos = data.get("ids_alumnos", [])
    semestre_destino = int(data.get("semestre_destino"))
    
    if not ids_alumnos or not semestre_destino:
        return jsonify({"error": "Faltan alumnos o semestre de destino"}), 400

    try:
        if semestre_destino > 6:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.estatus: 'EGRESADO', Alumno.semestre_actual: 6}, synchronize_session=False)
        else:
            # 1. Movemos a los alumnos al semestre elegido
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.semestre_actual: semestre_destino}, synchronize_session=False)

            # 🔥 2. MAGIA: Les asignamos la deuda del semestre al que acaban de llegar
            for id_alum in ids_alumnos:
                alumno = Alumno.query.get(id_alum)
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == semestre_destino,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).all()

                for c in conceptos:
                    existe = Pago.query.filter_by(id_alumno=id_alum, id_estructura=c.id_estructura).first()
                    if not existe:
                        db.session.add(Pago(
                            id_alumno=id_alum,
                            id_estructura=c.id_estructura,
                            estado='PENDIENTE'
                        ))

        db.session.commit()
        return jsonify({"message": f"Promoción a {semestre_destino}° exitosa y cobros generados"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/alumnos/<string:matricula>", methods=["DELETE", "OPTIONS"])
def eliminar_alumno(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    alumno = Alumno.query.filter_by(matricula=matricula).first()
    
    if not alumno: return jsonify({"error": "El alumno no existe"}), 404

    try:
        Pago.query.filter_by(id_alumno=alumno.id_alumno).delete()
        id_usuario_vinculado = alumno.id_usuario
        db.session.delete(alumno)
        db.session.flush() 
        if id_usuario_vinculado:
            Usuario.query.filter_by(id_usuario=id_usuario_vinculado).delete()

        db.session.commit()
        return jsonify({"message": f"Alumno {matricula} eliminado"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
# ==========================
# ✅ MÓDULO DE GENERACIONES (Con Meses Reales)
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
        db.session.flush() 

        # 🔥 Listas de meses según el calendario escolar
        meses_impares = ["AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        meses_pares = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO"]

        for sem in range(1, 7):
            # 1. Creamos la Inscripción
            db.session.add(EstructuraPago(
                id_generacion=nueva_gen.id_generacion, tipo='INSCRIPCION', semestre=sem,
                concepto=f'INSCRIPCIÓN {sem}° SEMESTRE', monto=3000
            ))

            # 2. Creamos las mensualidades con sus nombres reales
            meses_a_usar = meses_impares if sem % 2 != 0 else meses_pares
            
            for mes in meses_a_usar:
                db.session.add(EstructuraPago(
                    id_generacion=nueva_gen.id_generacion, tipo='MENSUALIDAD', semestre=sem,
                    concepto=f'MENSUALIDAD {mes} - {sem}° SEM', monto=1500
                ))

        db.session.commit()
        return jsonify({"message": "Generación y esquema de pagos base creados"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# ==========================
# 📋 LISTAR GENERACIONES (A prueba de fechas nulas)
# ==========================
@app.route("/generaciones", methods=["GET", "OPTIONS"])
def listar_generaciones():
    if request.method == "OPTIONS": return jsonify({}), 200
    generaciones = Generacion.query.all()
    resultado = []
    
    for g in generaciones:
        # Contamos activos y bajas leyendo la relación g.alumnos
        activos = sum(1 for a in g.alumnos if a.estatus == 'ACTIVO')
        bajas = sum(1 for a in g.alumnos if a.estatus in ['BAJA', 'SUSPENDIDO'])
        
        # 🔥 MAGIA: Validamos que la fecha exista antes de intentar formatearla
        fecha_ini_str = g.fecha_inicio.strftime("%Y-%m-%d") if g.fecha_inicio else ""
        fecha_fin_str = g.fecha_fin.strftime("%Y-%m-%d") if g.fecha_fin else ""
        
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": fecha_ini_str,  # Usamos la variable segura
            "fecha_fin": fecha_fin_str,     # Usamos la variable segura
            "estado": g.estado,
            "activos": activos, 
            "bajas": bajas
        })
    return jsonify(resultado), 200

# ✅ Ruta PUT para editar y cambiar estado ("Apagar" Generación)
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
# ==========================================
# 💰 MÓDULO FINANCIERO: ESTRUCTURA DE PAGOS
# ==========================================

@app.route("/estructura-pagos/<int:id_generacion>", methods=["GET"])
def obtener_estructura(id_generacion):
    try:
        # Buscamos todos los cobros programados para una generación específica
        conceptos = EstructuraPago.query.filter_by(id_generacion=id_generacion).all()
        resultado = []
        for c in conceptos:
            resultado.append({
                "id_estructura": c.id_estructura,
                "concepto": c.concepto,
                "monto": float(c.monto),
                "fecha_vencimiento": c.fecha_vencimiento.strftime("%Y-%m-%d") if c.fecha_vencimiento else None,
                "semestre_aplicable": c.semestre_aplicable
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/estructura-pagos", methods=["POST"])
def crear_concepto():
    data = request.get_json()
    
    campos_requeridos = ("id_generacion", "concepto", "monto", "semestre_aplicable", "fecha_vencimiento")
    if not all(k in data for k in campos_requeridos):
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    try:
        nuevo_concepto = EstructuraPago(
            id_generacion=data["id_generacion"],
            concepto=data["concepto"].upper(),
            monto=data["monto"],
            fecha_vencimiento=data["fecha_vencimiento"],
            semestre_aplicable=data["semestre_aplicable"]
        )
        db.session.add(nuevo_concepto)
        db.session.commit()
        return jsonify({"message": "Concepto de pago creado exitosamente"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route("/estructura-pagos/<int:id_estructura>", methods=["DELETE"])
def eliminar_concepto(id_estructura):
    concepto = EstructuraPago.query.get(id_estructura)
    if not concepto:
        return jsonify({"error": "Concepto no encontrado"}), 404
        
    try:
        db.session.delete(concepto)
        db.session.commit()
        return jsonify({"message": "Concepto eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "No se puede eliminar porque ya hay recibos cobrados con este concepto."}), 500    
# ==========================================
# 💵 MÓDULO DE CAJA (PUNTO DE COBRO)
# ==========================================

@app.route("/caja/deudas/<string:matricula>", methods=["GET"])
def obtener_deudas(matricula):
    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404

        # Simulamos la consulta a una tabla de 'deudas' o 'recibos' pendientes
        # Ajusta esto según cómo se llame tu tabla de pagos en MySQL
        pagos_pendientes = Pago.query.filter_by(id_alumno=alumno.id_alumno, estatus_pago='PENDIENTE').all()
        
        deudas = []
        for p in pagos_pendientes:
            deudas.append({
                "id_pago": p.id_pago,
                "concepto": p.concepto,
                "monto": float(p.monto_total),
                "fecha_limite": p.fecha_limite.strftime("%Y-%m-%d") if p.fecha_limite else None
            })

        return jsonify({
            "alumno": {
                "nombre_completo": f"{alumno.nombre} {alumno.apellido}",
                "grupo": alumno.id_grupo,
                "estatus": alumno.estatus
            },
            "deudas": deudas
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# ==========================================
# 💵 MÓDULO DE CAJA: LISTADO DE COBRO Y CAJA
# ==========================================
@app.route("/caja/alumnos", methods=["GET"])
def obtener_alumnos_caja():
    id_gen = request.args.get('generacion')
    if not id_gen or id_gen == '0':
        return jsonify({"error": "Debes seleccionar una generación"}), 400

    try:
        alumnos = Alumno.query.filter_by(id_generacion=id_gen).all()
        resultado = []
        for a in alumnos:
            mensualidades = db.session.query(Pago).join(EstructuraPago).filter(
                Pago.id_alumno == a.id_alumno,
                Pago.estado == 'PENDIENTE',
                EstructuraPago.concepto.like('%MENSUALIDAD%')
            ).count()

            extraordinarios = db.session.query(Pago).join(EstructuraPago).filter(
                Pago.id_alumno == a.id_alumno,
                Pago.estado == 'PENDIENTE',
                EstructuraPago.concepto.like('%EEE%')
            ).count()

            # 🔥 LA SOLUCIÓN: Buscamos el nombre del grupo usando la relación de BD
            nombre_del_grupo = a.grupo.nombre_grupo if a.grupo else "S/G"

            resultado.append({
                "nombre": f"{a.nombre} {a.apellido}",
                "matricula": a.matricula,
                "generacion": a.id_generacion,
                "grupo": nombre_del_grupo, # <--- AHORA MANDAMOS LA LETRA ("A", "B", etc.)
                "tiene_adeudo": (mensualidades + extraordinarios) > 0,
                "m_pendientes": mensualidades,
                "eee_pendientes": extraordinarios
            })

        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
import traceback

# ==========================================
# 📊 API: OBTENER HISTORIAL DE PAGOS (Ajuste para fecha cruda)
# ==========================================
@app.route("/caja/historial/<string:matricula>", methods=["GET", "OPTIONS"])
def historial_pagos(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

        historial = db.session.query(Pago, EstructuraPago).filter(
            Pago.id_estructura == EstructuraPago.id_estructura, Pago.id_alumno == alumno.id_alumno
        ).all()
        
        resultado = []
        for p, e in historial:
            categoria_str = e.tipo.value if hasattr(e.tipo, 'value') else str(e.tipo)
            estado_str = p.estado.value if hasattr(p.estado, 'value') else str(p.estado)
            
            # Formatos de fecha (uno para la vista, uno para el input de editar)
            fecha_formateada = p.fecha_pago.strftime("%d/%m/%Y") if p.fecha_pago else None
            fecha_raw = p.fecha_pago.strftime("%Y-%m-%d") if p.fecha_pago else None

            resultado.append({
                "id": p.id_pago, "concepto": e.concepto, "monto": float(e.monto) if e.monto is not None else 0.0,
                "semestre": e.semestre, "categoria": categoria_str.split('.')[-1], 
                "pagado": estado_str.split('.')[-1] == 'PAGADO',
                "fecha_pago": fecha_formateada, "fecha_raw": fecha_raw, "folio": p.folio # ✅ Agregamos fecha_raw
            })
        return jsonify(resultado), 200
    except Exception as err:
        return jsonify({"error": str(err)}), 500


# ==========================================
# 🔄 API: REVERTIR PAGO (APAGAR BOTÓN)
# ==========================================
@app.route("/caja/revertir/<int:id_pago>", methods=["PUT", "OPTIONS"])
def revertir_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404

        # Regresamos el estado a pendiente y borramos fecha/folio
        if hasattr(pago, 'estatus_pago'): pago.estatus_pago = 'PENDIENTE'
        else: pago.estado = 'PENDIENTE'
        
        pago.fecha_pago = None
        pago.folio = None

        db.session.commit()
        return jsonify({"message": "Pago cancelado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
# ==========================================
# 💸 API: REGISTRAR UN PAGO FÍSICO (Asentar Folio)
# ==========================================
@app.route("/caja/registrar", methods=["POST", "OPTIONS"])
def registrar_cobro_oficial():
    if request.method == "OPTIONS": 
        return jsonify({}), 200
        
    data = request.get_json()
    id_pago = data.get("id_pago")
    fecha_ingresada = data.get("fecha")
    folio_ingresado = data.get("folio")

    try:
        pago = Pago.query.get(id_pago)
        if not pago:
            return jsonify({"error": "Recibo no encontrado"}), 404

        # Cambiamos el estado a PAGADO
        if hasattr(pago, 'estatus_pago'):
            pago.estatus_pago = 'PAGADO'
        else:
            pago.estado = 'PAGADO'
            
        # Asignamos la fecha y folio que escribió la secretaria
        pago.fecha_pago = fecha_ingresada 
        pago.folio = folio_ingresado
        
        db.session.commit()
        return jsonify({"message": "Cobro asentado correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print("🔴 ERROR EN POST /registrar:", str(e))
        return jsonify({"error": str(e)}), 500

# ==========================================
# ➕ API: CREAR UN COBRO DESDE EL MODAL
# ==========================================
@app.route("/caja/crear", methods=["POST", "OPTIONS"])
def crear_pago_manual():
    if request.method == "OPTIONS": 
        return jsonify({}), 200

    data = request.get_json()
    try:
        alumno = Alumno.query.filter_by(matricula=data['matricula']).first()
        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404
        
        tipo_recibido = data.get('categoria') or data.get('tipo')
        if not tipo_recibido:
            return jsonify({"error": "Falta el tipo de cobro"}), 400

        nueva_estructura = EstructuraPago(
            id_generacion=alumno.id_generacion,
            tipo=tipo_recibido,
            semestre=data.get('semestre', 1),
            concepto=data['concepto'].upper(),
            monto=data['monto']
        )
        db.session.add(nueva_estructura)
        db.session.flush()

        nuevo_pago = Pago(
            id_alumno=alumno.id_alumno, 
            id_estructura=nueva_estructura.id_estructura,
            estado='PENDIENTE' 
        )

        db.session.add(nuevo_pago)
        db.session.commit()
        
        return jsonify({"message": "Cobro registrado correctamente"}), 201

    except Exception as err:
        db.session.rollback()
        print("🔴 ERROR EN POST /crear:", str(err))
        return jsonify({"error": str(err)}), 500
    
# ==========================================
# ✏️ API: EDITAR CUALQUIER DATO DE UN COBRO
# ==========================================
@app.route("/caja/pago/<int:id_pago>", methods=["PUT", "OPTIONS"])
def editar_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404
        
        # 1. Editar Monto y Concepto
        estructura = EstructuraPago.query.get(pago.id_estructura)
        if estructura:
            estructura.concepto = data.get("concepto", estructura.concepto).upper()
            estructura.monto = data.get("monto", estructura.monto)
            
        # 2. Editar Fecha y Folio (solo si ya estaba pagado)
        if getattr(pago, 'estado', '') == 'PAGADO' or getattr(pago, 'estatus_pago', '') == 'PAGADO':
            if "fecha" in data: pago.fecha_pago = data["fecha"]
            if "folio" in data: pago.folio = data["folio"]
            
        db.session.commit()
        return jsonify({"message": "Cobro actualizado"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🗑️ API: ELIMINAR UN COBRO PENDIENTE
# ==========================================
@app.route("/caja/pago/<int:id_pago>", methods=["DELETE", "OPTIONS"])
def eliminar_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404
        
        # Eliminamos el recibo pendiente del alumno
        db.session.delete(pago)
        db.session.commit()
        return jsonify({"message": "Cobro eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# ==========================================
# 🔐 API: ACTUALIZAR CONTRASEÑA (Usando SQLAlchemy)
# ==========================================
@app.route('/api/actualizar_password', methods=['POST', 'OPTIONS'])
def actualizar_password():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    try:
        data = request.get_json()
        
        # 1. Recibimos los datos
        correo = data.get('correoUsuario') 
        pass_actual = data.get('passActual')
        pass_nueva = data.get('passNueva')

        if not correo or not pass_actual or not pass_nueva:
            return jsonify({"status": "error", "mensaje": "Faltan datos por enviar"}), 400

        # 2. Buscamos al usuario usando el modelo SQLAlchemy
        usuario = Usuario.query.filter_by(correo=correo).first()

        if not usuario:
            return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404
        
        # 3. Verificamos la contraseña actual (Usando el mismo sistema que tienes en tu Login)
        if not check_password_hash(usuario.contraseña, pass_actual):
            return jsonify({"status": "error", "mensaje": "La contraseña actual es incorrecta"}), 401

        # 4. Encriptamos y guardamos la nueva contraseña
        usuario.contraseña = generate_password_hash(pass_nueva)
        db.session.commit()

        return jsonify({"status": "success", "mensaje": "Contraseña actualizada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        print("Error al actualizar contraseña:", str(e))
        return jsonify({"status": "error", "mensaje": "Error en el servidor al actualizar"}), 500      

# ==========================================
# 👤 API: ACTUALIZAR INFORMACIÓN PERSONAL
# ==========================================
@app.route('/api/actualizar_perfil', methods=['PUT', 'OPTIONS'])
def actualizar_perfil():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    try:
        data = request.get_json()
        
        correo_actual = data.get('correoActual') # Para saber a quién buscar
        nuevo_nombre = data.get('nombre')
        nuevo_correo = data.get('correo')
        nuevo_puesto = data.get('puesto')

        # 1. Buscamos al usuario por su correo actual
        usuario = Usuario.query.filter_by(correo=correo_actual).first()
        if not usuario:
            return jsonify({"status": "error", "mensaje": "Usuario no encontrado"}), 404

        # 2. Validamos si el nuevo correo ya lo está usando alguien más
        if nuevo_correo != correo_actual:
            existe = Usuario.query.filter_by(correo=nuevo_correo).first()
            if existe:
                return jsonify({"status": "error", "mensaje": "El nuevo correo ya está en uso"}), 400

        # 3. Guardamos los nuevos datos
        usuario.nombre = nuevo_nombre
        usuario.correo = nuevo_correo
        if hasattr(usuario, 'puesto') and nuevo_puesto:
            usuario.puesto = nuevo_puesto

        db.session.commit()
        return jsonify({"status": "success", "mensaje": "Información personal actualizada"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "mensaje": "Error en el servidor al actualizar"}), 500
# ==========================
# INICIO DE LA APP
# ==========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)