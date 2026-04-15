from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from extensions import db
from models import Alumno, Usuario, EstructuraPago, Pago, Bitacora
from routes.admin_routes import generar_password_alumno
from datetime import datetime 
from helpers import registrar_accion, obtener_id_admin
# 🛡️ IMPORTAMOS EL ESCUDO DE SEGURIDAD
from flask_jwt_extended import verify_jwt_in_request, get_jwt

alumno_bp = Blueprint('alumno_bp', __name__)

# ==========================
# MÓDULO DE ALUMNOS (Inscripción y Listado)
# ==========================
@alumno_bp.route("/alumnos", methods=["GET", "OPTIONS"])
def listar_alumnos():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        alumnos = Alumno.query.all()
        resultado = []
        for a in alumnos:
            nombre_gen = a.generacion.nombre if a.generacion else "Sin Generación"
            nombre_grupo = a.grupo.nombre_grupo if a.grupo else "Sin Grupo"
            
            resultado.append({
                "id_alumno": a.id_alumno,
                "matricula": a.matricula,
                "nombre": a.nombre,
                "apellido": a.apellido,
                "nombre_completo": f"{a.nombre} {a.apellido}",
                "estatus": a.estatus,
                "semestre_actual": a.semestre_actual,
                "id_generacion": a.id_generacion,
                "nombre_generacion": nombre_gen,
                "id_grupo": a.id_grupo,
                "nombre_grupo": nombre_grupo,
                "fecha_nacimiento": a.fecha_nacimiento.strftime('%Y-%m-%d') if a.fecha_nacimiento else None,
                "fecha_baja": a.fecha_baja.strftime('%Y-%m-%d') if a.fecha_baja else None
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@alumno_bp.route('/alumnos', methods=['POST', 'OPTIONS'])
def registrar_alumno_con_usuario():
    if request.method == 'OPTIONS': return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para inscribir alumnos"}), 403
        
    data = request.get_json()
    
    try:
        matricula_req = data.get('matricula')
        nombre_req = data.get('nombre')
        apellido_req = data.get('apellido')
        fecha_nac_req = data.get('fecha_nacimiento') 
        id_generacion_req = data.get('id_generacion')
        id_grupo_req = data.get('id_grupo')

        if not fecha_nac_req:
            return jsonify({'error': 'La fecha de nacimiento es obligatoria'}), 400

        alumno_existente = Alumno.query.filter_by(matricula=matricula_req).first()
        usuario_existente = Usuario.query.filter_by(correo=matricula_req).first()
        
        password_creada = generar_password_alumno(nombre_req, apellido_req, fecha_nac_req)

        if alumno_existente:
            if alumno_existente.estatus == 'ACTIVO':
                return jsonify({'error': 'Esta matrícula ya pertenece a un alumno ACTIVO.'}), 400
            
            alumno_existente.nombre = nombre_req
            alumno_existente.apellido = apellido_req
            alumno_existente.fecha_nacimiento = fecha_nac_req
            alumno_existente.id_generacion = id_generacion_req
            alumno_existente.id_grupo = id_grupo_req
            alumno_existente.estatus = 'ACTIVO'
            alumno_existente.semestre_actual = 1 
            alumno_existente.fecha_baja = None 
            
            if usuario_existente:
                usuario_existente.nombre = f"{nombre_req} {apellido_req}"
                usuario_existente.contraseña = generate_password_hash(password_creada)
                usuario_existente.estado = "ACTIVO"

            Pago.query.filter_by(id_alumno=alumno_existente.id_alumno, estado='PENDIENTE').update({
                'estado': 'CANCELADO' 
            })
            
            target_alumno = alumno_existente
            mensaje_log = f"RE-INSCRIPCIÓN: Alumno {matricula_req} reingresado a Gen {id_generacion_req}"

        else:
            nuevo_usuario = Usuario(
                nombre=f"{nombre_req} {apellido_req}",
                correo=matricula_req,
                contraseña=generate_password_hash(password_creada),
                rol="ALUMNO",
                estado="ACTIVO"
            )
            db.session.add(nuevo_usuario)
            db.session.flush() 

            nuevo_alumno = Alumno(
                matricula=matricula_req,
                nombre=nombre_req,
                apellido=apellido_req,
                fecha_nacimiento=fecha_nac_req,
                id_generacion=id_generacion_req,
                id_grupo=id_grupo_req,
                id_usuario=nuevo_usuario.id_usuario,
                estatus="ACTIVO",
                semestre_actual=1 
            )
            db.session.add(nuevo_alumno)
            db.session.flush()
            
            target_alumno = nuevo_alumno
            mensaje_log = f"NUEVO ALUMNO: {matricula_req} ({nombre_req} {apellido_req}) inscrito"

        estructuras_nuevas = EstructuraPago.query.filter_by(id_generacion=id_generacion_req).all()
        for molde in estructuras_nuevas:
            nuevo_pago = Pago(
                id_alumno=target_alumno.id_alumno,
                id_estructura=molde.id_estructura,
                estado='PENDIENTE',
                numero_oportunidad=1
            )
            db.session.add(nuevo_pago)
        
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="INSCRIPCION_ALUMNO",
            descripcion=mensaje_log
        )

        return jsonify({
            'message': 'Proceso completado con éxito', 
            'password_generada': password_creada
        }), 201

    except Exception as e:
        db.session.rollback()
        print("🔴 Error:", str(e))
        return jsonify({'error': 'Error al procesar la inscripción'}), 500

# ==========================================
# ✏️ ACTUALIZAR ALUMNO
# ==========================================
@alumno_bp.route("/alumnos/<string:matricula_original>", methods=["PUT", "OPTIONS"])
def actualizar_estatus_alumno(matricula_original):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para editar alumnos"}), 403

    data = request.get_json()
    
    alumno = Alumno.query.filter_by(matricula=matricula_original).first()
    if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

    try:
        nueva_matricula = data.get("matricula")
        if nueva_matricula and nueva_matricula != matricula_original:
            existe = Alumno.query.filter_by(matricula=nueva_matricula).first()
            if existe: return jsonify({"error": "La nueva matrícula ya está en uso"}), 400
            
            if alumno.id_usuario:
                usuario = Usuario.query.get(alumno.id_usuario)
                if usuario: usuario.correo = nueva_matricula
            alumno.matricula = nueva_matricula

        if "nombre" in data: alumno.nombre = data["nombre"]
        if "apellido" in data: alumno.apellido = data["apellido"]
        if "id_grupo" in data: alumno.id_grupo = data["id_grupo"]

        if "estatus" in data:
            estatus_nuevo = data["estatus"]
            
            if estatus_nuevo == 'BAJA':
                fecha_baja_str = data.get("fecha_baja")
                if fecha_baja_str:
                    fecha_baja = datetime.strptime(fecha_baja_str, "%Y-%m-%d").date()
                else:
                    fecha_baja = datetime.now().date()
                    
                alumno.fecha_baja = fecha_baja
                
                pagos_pendientes = db.session.query(Pago, EstructuraPago).join(
                    EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
                ).filter(
                    Pago.id_alumno == alumno.id_alumno,
                    Pago.estado == 'PENDIENTE',
                    EstructuraPago.tipo == 'MENSUALIDAD'
                ).all()

                for p, e in pagos_pendientes:
                    if e.anio > fecha_baja.year or (e.anio == fecha_baja.year and e.mes > fecha_baja.month):
                        db.session.delete(p)

            elif estatus_nuevo != 'BAJA' and alumno.estatus == 'BAJA':
                alumno.fecha_baja = None 
                
            alumno.estatus = estatus_nuevo

        nuevo_sem_req = data.get("semestre_actual") or data.get("semestre")
        
        if nuevo_sem_req is not None:
            nuevo_semestre = int(nuevo_sem_req)
            if nuevo_semestre != alumno.semestre_actual:
                alumno.semestre_actual = nuevo_semestre 
                
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == nuevo_semestre,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).all()

                for c in conceptos:
                    existe_pago = Pago.query.filter_by(id_alumno=alumno.id_alumno, id_estructura=c.id_estructura).first()
                    if not existe_pago:
                        db.session.add(Pago(
                            id_alumno=alumno.id_alumno,
                            id_estructura=c.id_estructura,
                            estado='PENDIENTE',
                            numero_oportunidad=1
                        ))

        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_ALUMNO",
            descripcion=f"Modificó la información o el estatus del alumno {alumno.matricula}"
        )

        return jsonify({"message": "Datos actualizados correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# 🚀 PROMOCIÓN MASIVA 
# ==========================
@alumno_bp.route("/alumnos/promocion-masiva", methods=["POST", "OPTIONS"])
def promocion_masiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para realizar promociones"}), 403

    data = request.get_json()
    id_gen = data.get("id_generacion")
    
    if not id_gen: return jsonify({"error": "Debes especificar la generación"}), 400

    try:
        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual == 6, Alumno.estatus == 'ACTIVO'
        ).update({Alumno.estatus: 'EGRESADO'}, synchronize_session=False)

        alumnos_a_promover = Alumno.query.filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual < 6, Alumno.estatus == 'ACTIVO'
        ).all()

        cantidad_promovidos = len(alumnos_a_promover)

        for alumno in alumnos_a_promover:
            alumno.semestre_actual += 1

        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="PROMOCION_MASIVA",
            descripcion=f"Promovió masivamente a {cantidad_promovidos} alumnos de la generación ID: {id_gen}"
        )

        return jsonify({"message": "Promoción completada"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 

# ==========================
# 🎯 PROMOCIÓN SELECTIVA
# ==========================
@alumno_bp.route("/alumnos/promocion-selectiva", methods=["POST", "OPTIONS"])
def promocion_selectiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para realizar promociones"}), 403

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
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.semestre_actual: semestre_destino}, synchronize_session=False)

        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="PROMOCION_SELECTIVA",
            descripcion=f"Promovió manualmente a {len(ids_alumnos)} alumno(s) al semestre {semestre_destino}"
        )

        return jsonify({"message": f"Promoción a {semestre_destino}° exitosa"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# ❌ ELIMINAR ALUMNO
# ==========================
@alumno_bp.route("/alumnos/<string:matricula>", methods=["DELETE", "OPTIONS"])
def eliminar_alumno(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL (SOLO SISTEMAS)
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede eliminar registros físicos de alumnos"}), 403

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

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_ALUMNO",
            descripcion=f"Eliminó por completo los registros del alumno con matrícula {matricula}"
        )

        return jsonify({"message": f"Alumno {matricula} eliminado"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🔓 API: LIBERAR MATRÍCULA PARA REINGRESO
# ==========================================
@alumno_bp.route("/alumnos/liberar-matricula/<string:matricula>", methods=["POST", "OPTIONS"])
def liberar_matricula(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para liberar matrículas"}), 403

    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno: 
            return jsonify({"error": "Alumno no encontrado"}), 404
            
        if alumno.estatus != 'BAJA':
            return jsonify({"error": "El alumno debe estar dado de baja primero."}), 400

        nueva_matricula = f"{matricula}-BAJA"
        alumno.matricula = nueva_matricula

        usuario_login = Usuario.query.filter_by(correo=matricula).first()
        if usuario_login:
            usuario_login.correo = nueva_matricula

        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="LIBERAR_MATRICULA",
            descripcion=f"Liberó la matrícula {matricula} cambiándola a {nueva_matricula}"
        )

        return jsonify({"message": "Matrícula archivada y liberada exitosamente."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🎓 API: ESTADO DE CUENTA DEL ALUMNO (PORTAL)
# ==========================================
# 🔥 CAMBIO AQUÍ: Agregamos /portal/ para que no choque con <matricula>
@alumno_bp.route('/alumnos/portal/mi-estado-cuenta', methods=['GET', 'OPTIONS'])
def obtener_mi_estado_cuenta():
    if request.method == "OPTIONS": return jsonify({}), 200

    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: 
        verify_jwt_in_request()
    except Exception: 
        return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'ALUMNO':
        return jsonify({"error": "Solo los alumnos pueden ver su estado de cuenta personal"}), 403

    try:
        # 1. Obtener la identidad del token
        usuario_actual = operador.get('sub') 
        print(f"🔥 DEBUG TOKEN: La identidad del token es -> {usuario_actual}")

        # 2. BÚSQUEDA INTELIGENTE DE USUARIO
        # Intento A: ¿El token guardó el correo / matrícula?
        usuario = Usuario.query.filter_by(correo=str(usuario_actual)).first()
        
        # Intento B: Si falló, ¿quizás el token guardó el ID numérico del usuario?
        if not usuario:
            usuario = Usuario.query.filter_by(id_usuario=usuario_actual).first()

        if not usuario:
            print("❌ ERROR: No existe ningún usuario con ese dato en la BD.")
            return jsonify({"message": "Usuario no encontrado"}), 404

        print(f"✅ ÉXITO: Usuario encontrado -> {usuario.nombre}")

        # 3. BÚSQUEDA INTELIGENTE DEL ALUMNO
        # Intento A: Buscar por el enlace directo de llaves foráneas
        alumno = Alumno.query.filter_by(id_usuario=usuario.id_usuario).first()
        
        # Intento B: Si por algún error de base de datos no está enlazado el ID, buscamos por matrícula
        if not alumno:
            alumno = Alumno.query.filter_by(matricula=usuario.correo).first()

        if not alumno:
            print("❌ ERROR: El usuario existe, pero no está registrado como Alumno.")
            return jsonify({"message": "Alumno no encontrado para este usuario"}), 404

        print(f"✅ ÉXITO: Alumno enlazado -> {alumno.matricula}")

        # 4. Buscar todos los pagos de este alumno
        pagos = Pago.query.filter_by(id_alumno=alumno.id_alumno).all()

        # 5. Formatear los datos principales
        nombre_grupo = "S/G"
        if alumno.grupo:
            # Revisa si tu modelo Grupo usa .nombre o .nombre_grupo
            nombre_grupo = getattr(alumno.grupo, 'nombre_grupo', getattr(alumno.grupo, 'nombre', 'S/G'))

        datos_alumno = {
            "nombre": f"{alumno.nombre} {alumno.apellido}",
            "matricula": alumno.matricula,
            "grupo": nombre_grupo,
            "semestre_actual": alumno.semestre_actual
        }

       # 6. Formatear los pagos
        historial_pagos = []
        for p in pagos:
            estructura = EstructuraPago.query.get(p.id_estructura)
            
            historial_pagos.append({
                "id": p.id_pago if hasattr(p, 'id_pago') else getattr(p, 'id', None),
                "concepto": estructura.concepto if estructura else "Pago",
                "categoria": estructura.tipo if estructura else "Otro",
                
                # 🔥 CORRECCIÓN DEL $0.00 AQUÍ: Tomamos el costo total desde la "Estructura"
                "monto": estructura.monto if estructura else 0, 
                
                "restante": p.restante if hasattr(p, 'restante') else getattr(p, 'monto_restante', 0),
                "pagado": True if p.estado == 'PAGADO' else False,
                "es_parcial": True if p.estado == 'ABONADO' else False,
                "folio": getattr(p, 'folio_recibo', getattr(p, 'folio', None)),
                "fecha_pago": p.fecha_pago.strftime('%Y-%m-%d') if p.fecha_pago else None,
                "semestre": estructura.semestre if estructura else 1
            })
            
        return jsonify({
            "alumno": datos_alumno,
            "pagos": historial_pagos
        }), 200

    except Exception as e:
        print(f"🔴 Error interno en mi-estado-cuenta: {str(e)}")
        return jsonify({"message": "Error interno del servidor", "detalle": str(e)}), 500


""" 2 from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from extensions import db
from models import Alumno, Usuario, EstructuraPago, Pago, Bitacora
from routes.admin_routes import generar_password_alumno
from datetime import datetime 
# 📸 IMPORTAMOS LAS HERRAMIENTAS DE LA BITÁCORA
from helpers import registrar_accion, obtener_id_admin

alumno_bp = Blueprint('alumno_bp', __name__)

# ==========================
# MÓDULO DE ALUMNOS (Inscripción y Listado)
# ==========================
@alumno_bp.route("/alumnos", methods=["GET"])
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
                "nombre": a.nombre,
                "apellido": a.apellido,
                "nombre_completo": f"{a.nombre} {a.apellido}",
                "estatus": a.estatus,
                "semestre_actual": a.semestre_actual,
                "id_generacion": a.id_generacion,
                "nombre_generacion": nombre_gen,
                "id_grupo": a.id_grupo,
                "nombre_grupo": nombre_grupo,
                "fecha_nacimiento": a.fecha_nacimiento.strftime('%Y-%m-%d') if a.fecha_nacimiento else None,
                "fecha_baja": a.fecha_baja.strftime('%Y-%m-%d') if a.fecha_baja else None
            })
        return jsonify(resultado), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@alumno_bp.route('/alumnos', methods=['POST', 'OPTIONS'])
def registrar_alumno_con_usuario():
    if request.method == 'OPTIONS': return jsonify({}), 200
        
    data = request.get_json()
    
    try:
        matricula_req = data.get('matricula')
        nombre_req = data.get('nombre')
        apellido_req = data.get('apellido')
        fecha_nac_req = data.get('fecha_nacimiento') 
        id_generacion_req = data.get('id_generacion')
        id_grupo_req = data.get('id_grupo')

        if not fecha_nac_req:
            return jsonify({'error': 'La fecha de nacimiento es obligatoria'}), 400

        alumno_existente = Alumno.query.filter_by(matricula=matricula_req).first()
        usuario_existente = Usuario.query.filter_by(correo=matricula_req).first()
        
        password_creada = generar_password_alumno(nombre_req, apellido_req, fecha_nac_req)

        if alumno_existente:
            if alumno_existente.estatus == 'ACTIVO':
                return jsonify({'error': 'Esta matrícula ya pertenece a un alumno ACTIVO.'}), 400
            
            alumno_existente.nombre = nombre_req
            alumno_existente.apellido = apellido_req
            alumno_existente.fecha_nacimiento = fecha_nac_req
            alumno_existente.id_generacion = id_generacion_req
            alumno_existente.id_grupo = id_grupo_req
            alumno_existente.estatus = 'ACTIVO'
            alumno_existente.semestre_actual = 1 
            alumno_existente.fecha_baja = None 
            
            if usuario_existente:
                usuario_existente.nombre = f"{nombre_req} {apellido_req}"
                usuario_existente.contraseña = generate_password_hash(password_creada)
                usuario_existente.estado = "ACTIVO"

            Pago.query.filter_by(id_alumno=alumno_existente.id_alumno, estado='PENDIENTE').update({
                'estado': 'CANCELADO' 
            })
            
            target_alumno = alumno_existente
            mensaje_log = f"RE-INSCRIPCIÓN: Alumno {matricula_req} reingresado a Gen {id_generacion_req}"

        else:
            nuevo_usuario = Usuario(
                nombre=f"{nombre_req} {apellido_req}",
                correo=matricula_req,
                contraseña=generate_password_hash(password_creada),
                rol="ALUMNO",
                estado="ACTIVO"
            )
            db.session.add(nuevo_usuario)
            db.session.flush() 

            nuevo_alumno = Alumno(
                matricula=matricula_req,
                nombre=nombre_req,
                apellido=apellido_req,
                fecha_nacimiento=fecha_nac_req,
                id_generacion=id_generacion_req,
                id_grupo=id_grupo_req,
                id_usuario=nuevo_usuario.id_usuario,
                estatus="ACTIVO",
                semestre_actual=1 
            )
            db.session.add(nuevo_alumno)
            db.session.flush()
            
            target_alumno = nuevo_alumno
            mensaje_log = f"NUEVO ALUMNO: {matricula_req} ({nombre_req} {apellido_req}) inscrito"

        estructuras_nuevas = EstructuraPago.query.filter_by(id_generacion=id_generacion_req).all()
        for molde in estructuras_nuevas:
            nuevo_pago = Pago(
                id_alumno=target_alumno.id_alumno,
                id_estructura=molde.id_estructura,
                estado='PENDIENTE',
                numero_oportunidad=1
            )
            db.session.add(nuevo_pago)
        
        db.session.commit()

        # 📸 BITÁCORA: Inscripción o Re-inscripción
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="INSCRIPCION_ALUMNO",
            descripcion=mensaje_log
        )

        return jsonify({
            'message': 'Proceso completado con éxito', 
            'password_generada': password_creada
        }), 201

    except Exception as e:
        db.session.rollback()
        print("🔴 Error:", str(e))
        return jsonify({'error': 'Error al procesar la inscripción'}), 500

# ==========================================
# ✏️ ACTUALIZAR ALUMNO
# ==========================================
@alumno_bp.route("/alumnos/<string:matricula_original>", methods=["PUT", "OPTIONS"])
def actualizar_estatus_alumno(matricula_original):
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    
    alumno = Alumno.query.filter_by(matricula=matricula_original).first()
    if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

    try:
        nueva_matricula = data.get("matricula")
        if nueva_matricula and nueva_matricula != matricula_original:
            existe = Alumno.query.filter_by(matricula=nueva_matricula).first()
            if existe: return jsonify({"error": "La nueva matrícula ya está en uso"}), 400
            
            if alumno.id_usuario:
                usuario = Usuario.query.get(alumno.id_usuario)
                if usuario: usuario.correo = nueva_matricula
            alumno.matricula = nueva_matricula

        if "nombre" in data: alumno.nombre = data["nombre"]
        if "apellido" in data: alumno.apellido = data["apellido"]
        if "id_grupo" in data: alumno.id_grupo = data["id_grupo"]

        if "estatus" in data:
            estatus_nuevo = data["estatus"]
            
            if estatus_nuevo == 'BAJA':
                fecha_baja_str = data.get("fecha_baja")
                if fecha_baja_str:
                    fecha_baja = datetime.strptime(fecha_baja_str, "%Y-%m-%d").date()
                else:
                    fecha_baja = datetime.now().date()
                    
                alumno.fecha_baja = fecha_baja
                
                pagos_pendientes = db.session.query(Pago, EstructuraPago).join(
                    EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
                ).filter(
                    Pago.id_alumno == alumno.id_alumno,
                    Pago.estado == 'PENDIENTE',
                    EstructuraPago.tipo == 'MENSUALIDAD'
                ).all()

                for p, e in pagos_pendientes:
                    if e.anio > fecha_baja.year or (e.anio == fecha_baja.year and e.mes > fecha_baja.month):
                        db.session.delete(p)

            elif estatus_nuevo != 'BAJA' and alumno.estatus == 'BAJA':
                alumno.fecha_baja = None 
                
            alumno.estatus = estatus_nuevo

        nuevo_sem_req = data.get("semestre_actual") or data.get("semestre")
        
        if nuevo_sem_req is not None:
            nuevo_semestre = int(nuevo_sem_req)
            if nuevo_semestre != alumno.semestre_actual:
                alumno.semestre_actual = nuevo_semestre 
                
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == nuevo_semestre,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).all()

                for c in conceptos:
                    existe_pago = Pago.query.filter_by(id_alumno=alumno.id_alumno, id_estructura=c.id_estructura).first()
                    if not existe_pago:
                        db.session.add(Pago(
                            id_alumno=alumno.id_alumno,
                            id_estructura=c.id_estructura,
                            estado='PENDIENTE',
                            numero_oportunidad=1
                        ))

        db.session.commit()

        # 📸 BITÁCORA: Modificación de alumno
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_ALUMNO",
            descripcion=f"Modificó la información o el estatus del alumno {alumno.matricula}"
        )

        return jsonify({"message": "Datos actualizados correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# 🚀 PROMOCIÓN MASIVA (VERSIÓN ORIGINAL LIMPIA)
# ==========================
@alumno_bp.route("/alumnos/promocion-masiva", methods=["POST", "OPTIONS"])
def promocion_masiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    id_gen = data.get("id_generacion")
    
    if not id_gen: return jsonify({"error": "Debes especificar la generación"}), 400

    try:
        # 1. Los de 6to pasan a EGRESADO
        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual == 6, Alumno.estatus == 'ACTIVO'
        ).update({Alumno.estatus: 'EGRESADO'}, synchronize_session=False)

        # 2. Los demás suben 1 semestre
        alumnos_a_promover = Alumno.query.filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual < 6, Alumno.estatus == 'ACTIVO'
        ).all()

        cantidad_promovidos = len(alumnos_a_promover)

        for alumno in alumnos_a_promover:
            alumno.semestre_actual += 1

        # ❌ ELIMINAMOS EL CÓDIGO QUE CREABA PAGOS. 
        # Ahora solo actualiza el número de semestre, respetando los 18 meses iniciales.

        db.session.commit()

        # 📸 BITÁCORA
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="PROMOCION_MASIVA",
            descripcion=f"Promovió masivamente a {cantidad_promovidos} alumnos de la generación ID: {id_gen}"
        )

        return jsonify({"message": "Promoción completada"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 

# ==========================
# 🎯 PROMOCIÓN SELECTIVA (VERSIÓN ORIGINAL LIMPIA)
# ==========================
@alumno_bp.route("/alumnos/promocion-selectiva", methods=["POST", "OPTIONS"])
def promocion_selectiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    ids_alumnos = data.get("ids_alumnos", [])
    semestre_destino = int(data.get("semestre_destino"))
    
    if not ids_alumnos or not semestre_destino:
        return jsonify({"error": "Faltan alumnos o semestre de destino"}), 400

    try:
        # 1. Actualizar el semestre
        if semestre_destino > 6:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.estatus: 'EGRESADO', Alumno.semestre_actual: 6}, synchronize_session=False)
        else:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.semestre_actual: semestre_destino}, synchronize_session=False)

        # ❌ ELIMINAMOS EL CÓDIGO QUE CREABA PAGOS TAMBIÉN AQUÍ.

        db.session.commit()

        # 📸 BITÁCORA
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="PROMOCION_SELECTIVA",
            descripcion=f"Promovió manualmente a {len(ids_alumnos)} alumno(s) al semestre {semestre_destino}"
        )

        return jsonify({"message": f"Promoción a {semestre_destino}° exitosa"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# ❌ ELIMINAR ALUMNO
# ==========================
@alumno_bp.route("/alumnos/<string:matricula>", methods=["DELETE", "OPTIONS"])
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

        # 📸 BITÁCORA: Borrar alumno
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_ALUMNO",
            descripcion=f"Eliminó por completo los registros del alumno con matrícula {matricula}"
        )

        return jsonify({"message": f"Alumno {matricula} eliminado"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🔓 API: LIBERAR MATRÍCULA PARA REINGRESO
# ==========================================
@alumno_bp.route("/alumnos/liberar-matricula/<string:matricula>", methods=["POST", "OPTIONS"])
def liberar_matricula(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno: 
            return jsonify({"error": "Alumno no encontrado"}), 404
            
        if alumno.estatus != 'BAJA':
            return jsonify({"error": "El alumno debe estar dado de baja primero."}), 400

        nueva_matricula = f"{matricula}-BAJA"
        alumno.matricula = nueva_matricula

        usuario_login = Usuario.query.filter_by(correo=matricula).first()
        if usuario_login:
            usuario_login.correo = nueva_matricula

        db.session.commit()

        # 📸 BITÁCORA: Liberar Matrícula
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="LIBERAR_MATRICULA",
            descripcion=f"Liberó la matrícula {matricula} cambiándola a {nueva_matricula}"
        )

        return jsonify({"message": "Matrícula archivada y liberada exitosamente."}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500   """  
    













""" 3 from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from extensions import db
from models import Alumno, Usuario, EstructuraPago, Pago
from datetime import datetime

alumno_bp = Blueprint('alumno_bp', __name__)

# Diccionario Global para Nombres de Meses
NOMBRES_MESES = {
    1: "ENERO", 2: "FEBRERO", 3: "MARZO", 4: "ABRIL", 5: "MAYO", 6: "JUNIO", 
    7: "JULIO", 8: "AGOSTO", 9: "SEPTIEMBRE", 10: "OCTUBRE", 11: "NOVIEMBRE", 12: "DICIEMBRE"
}

# ==========================
# MÓDULO DE ALUMNOS (Inscripción y Listado)
# ==========================
@alumno_bp.route("/alumnos", methods=["GET"])
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
                "nombre": a.nombre,
                "apellido": a.apellido,
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
    
@alumno_bp.route("/alumnos", methods=["POST", "OPTIONS"])
def registrar_alumno():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()

    try:
        nuevo_usuario = Usuario(
            nombre=f"{data['nombre']} {data['apellido']}",
            correo=data["matricula"],
            contraseña=generate_password_hash(data["matricula"]),
            rol='ALUMNO'
        )
        db.session.add(nuevo_usuario)
        db.session.flush() 

        sem_actual = int(data.get('semestre', 1))
        nuevo_alumno = Alumno(
            matricula=data["matricula"],
            nombre=data["nombre"],
            apellido=data["apellido"],
            id_generacion=data["id_generacion"],
            id_grupo=data["id_grupo"], 
            id_usuario=nuevo_usuario.id_usuario,
            semestre_actual=sem_actual, 
            estatus='ACTIVO'
        )
        db.session.add(nuevo_alumno)
        db.session.flush()

        # 🔥 LA REGLA DE ORO DE LOS MESES
        meses_nones = [8, 9, 10, 11, 12]          # 5 meses para 1, 3, 5
        meses_pares = [1, 2, 3, 4, 5, 6, 7]       # 7 meses para 2, 4, 6 (Hasta Julio)
        
        anio_actual = datetime.now().year
        es_par = (sem_actual % 2 == 0)
        meses_lista = meses_pares if es_par else meses_nones

        conceptos = EstructuraPago.query.filter(
            EstructuraPago.id_generacion == data["id_generacion"],
            EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD']),
            EstructuraPago.semestre == sem_actual
        ).order_by(EstructuraPago.id_estructura).all()

        idx_mes = 0
        for c in conceptos:
            tipo_str = str(c.tipo).upper()
            if 'MENSUALIDAD' in tipo_str:
                if idx_mes >= len(meses_lista):
                    continue 
                
                num_mes_real = meses_lista[idx_mes]
                c.mes = num_mes_real
                c.anio = anio_actual
                c.concepto = f"{NOMBRES_MESES[num_mes_real]} - {sem_actual}° SEM"
                db.session.add(c)
                
                nuevo_pago = Pago(
                    id_alumno=nuevo_alumno.id_alumno,
                    id_estructura=c.id_estructura,
                    estado='PENDIENTE',
                    numero_oportunidad=1
                )
                db.session.add(nuevo_pago)
                idx_mes += 1
            else:
                nuevo_pago = Pago(
                    id_alumno=nuevo_alumno.id_alumno,
                    id_estructura=c.id_estructura,
                    estado='PENDIENTE',
                    numero_oportunidad=1
                )
                db.session.add(nuevo_pago)

        db.session.commit()
        return jsonify({"message": "Inscripción exitosa"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# ✏️ ACTUALIZAR ALUMNO (Con Auto-Generación de Deuda)
# ==========================================
@alumno_bp.route("/alumnos/<string:matricula_original>", methods=["PUT", "OPTIONS"])
def actualizar_estatus_alumno(matricula_original):
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    
    alumno = Alumno.query.filter_by(matricula=matricula_original).first()
    if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

    try:
        nueva_matricula = data.get("matricula")
        if nueva_matricula and nueva_matricula != matricula_original:
            existe = Alumno.query.filter_by(matricula=nueva_matricula).first()
            if existe: return jsonify({"error": "La nueva matrícula ya está en uso"}), 400
            
            if alumno.id_usuario:
                usuario = Usuario.query.get(alumno.id_usuario)
                if usuario: usuario.correo = nueva_matricula
            alumno.matricula = nueva_matricula

        if "nombre" in data: alumno.nombre = data["nombre"]
        if "apellido" in data: alumno.apellido = data["apellido"]
        if "estatus" in data: alumno.estatus = data["estatus"]
        if "id_grupo" in data: alumno.id_grupo = data["id_grupo"]

        if "semestre_actual" in data:
            nuevo_semestre = int(data["semestre_actual"])
            
            if nuevo_semestre != alumno.semestre_actual:
                alumno.semestre_actual = nuevo_semestre 
                
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == nuevo_semestre,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).order_by(EstructuraPago.id_estructura).all()

                anio_actual = datetime.now().year
                meses_lista = [1, 2, 3, 4, 5, 6, 7] if nuevo_semestre % 2 == 0 else [8, 9, 10, 11, 12]
                idx_mes = 0

                for c in conceptos:
                    tipo_str = str(c.tipo).upper()
                    if 'MENSUALIDAD' in tipo_str:
                        if idx_mes < len(meses_lista):
                            m_real = meses_lista[idx_mes]
                            c.mes = m_real
                            c.anio = anio_actual
                            c.concepto = f"{NOMBRES_MESES[m_real]} - {nuevo_semestre}° SEM"
                            db.session.add(c)
                            idx_mes += 1
                        else: continue

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
# 🚀 PROMOCIÓN MASIVA
# ==========================
@alumno_bp.route("/alumnos/promocion-masiva", methods=["POST", "OPTIONS"])
def promocion_masiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    id_gen = data.get("id_generacion")
    
    if not id_gen: return jsonify({"error": "Debes especificar la generación"}), 400

    try:
        anio_actual = datetime.now().year

        db.session.query(Alumno).filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual == 6, Alumno.estatus == 'ACTIVO'
        ).update({Alumno.estatus: 'EGRESADO'}, synchronize_session=False)

        alumnos_a_promover = Alumno.query.filter(
            Alumno.id_generacion == id_gen, Alumno.semestre_actual < 6, Alumno.estatus == 'ACTIVO'
        ).all()

        for alumno in alumnos_a_promover:
            nuevo_semestre = alumno.semestre_actual + 1
            alumno.semestre_actual = nuevo_semestre

            conceptos = EstructuraPago.query.filter(
                EstructuraPago.id_generacion == id_gen,
                EstructuraPago.semestre == nuevo_semestre,
                EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
            ).order_by(EstructuraPago.id_estructura).all()

            meses_lista = [1, 2, 3, 4, 5, 6, 7] if nuevo_semestre % 2 == 0 else [8, 9, 10, 11, 12]
            idx_mes = 0

            for c in conceptos:
                tipo_str = str(c.tipo).upper()
                if 'MENSUALIDAD' in tipo_str:
                    if idx_mes < len(meses_lista):
                        m_real = meses_lista[idx_mes]
                        c.mes = m_real
                        c.anio = anio_actual
                        c.concepto = f"{NOMBRES_MESES[m_real]} - {nuevo_semestre}° SEM"
                        db.session.add(c)
                        idx_mes += 1
                    else: continue

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
# 🎯 PROMOCIÓN SELECTIVA
# ==========================
@alumno_bp.route("/alumnos/promocion-selectiva", methods=["POST", "OPTIONS"])
def promocion_selectiva():
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    ids_alumnos = data.get("ids_alumnos", [])
    semestre_destino = int(data.get("semestre_destino"))
    
    if not ids_alumnos or not semestre_destino:
        return jsonify({"error": "Faltan alumnos o semestre de destino"}), 400

    try:
        anio_actual = datetime.now().year

        if semestre_destino > 6:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.estatus: 'EGRESADO', Alumno.semestre_actual: 6}, synchronize_session=False)
        else:
            db.session.query(Alumno).filter(Alumno.id_alumno.in_(ids_alumnos))\
                .update({Alumno.semestre_actual: semestre_destino}, synchronize_session=False)

            meses_lista = [1, 2, 3, 4, 5, 6, 7] if semestre_destino % 2 == 0 else [8, 9, 10, 11, 12]

            for id_alum in ids_alumnos:
                alumno = Alumno.query.get(id_alum)
                conceptos = EstructuraPago.query.filter(
                    EstructuraPago.id_generacion == alumno.id_generacion,
                    EstructuraPago.semestre == semestre_destino,
                    EstructuraPago.tipo.in_(['INSCRIPCION', 'MENSUALIDAD'])
                ).order_by(EstructuraPago.id_estructura).all()

                idx_mes = 0
                for c in conceptos:
                    tipo_str = str(c.tipo).upper()
                    if 'MENSUALIDAD' in tipo_str:
                        if idx_mes < len(meses_lista):
                            m_real = meses_lista[idx_mes]
                            c.mes = m_real
                            c.anio = anio_actual
                            c.concepto = f"{NOMBRES_MESES[m_real]} - {semestre_destino}° SEM"
                            db.session.add(c)
                            idx_mes += 1
                        else: continue

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

@alumno_bp.route("/alumnos/<string:matricula>", methods=["DELETE", "OPTIONS"])
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
        return jsonify({"error": str(e)}), 500 """