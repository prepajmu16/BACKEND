from flask import Blueprint, request, jsonify
from extensions import db
from models import Generacion, Grupo, EstructuraPago, Alumno
from datetime import datetime
import re
from helpers import registrar_accion, obtener_id_admin
# 🛡️ IMPORTAMOS EL ESCUDO DE SEGURIDAD
from flask_jwt_extended import verify_jwt_in_request, get_jwt

catalogo_bp = Blueprint('catalogo_bp', __name__)

# ==========================
# ✅ MÓDULO DE GENERACIONES (Con Plantillas Nativas Inteligentes)
# ==========================
@catalogo_bp.route("/generaciones", methods=["POST", "OPTIONS"])
def registrar_generacion():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para crear generaciones"}), 403

    data = request.get_json()
    nombre_gen = data["nombre"].strip()
    
    try:
        # 🛡️ VALIDACIÓN: ¿Ya existe esta generación?
        existe = Generacion.query.filter_by(nombre=nombre_gen).first()
        if existe:
            return jsonify({"error": f"La generación '{nombre_gen}' ya existe."}), 400

        nueva_gen = Generacion(
            nombre=nombre_gen,
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            estado=data.get("estado", "ACTIVA")
        )
        db.session.add(nueva_gen)
        db.session.flush() 

        # 🧠 LÓGICA DE PAGOS MEJORADA
        meses_impares = [(8, "AGOSTO"), (9, "SEPTIEMBRE"), (10, "OCTUBRE"), (11, "NOVIEMBRE"), (12, "DICIEMBRE")]
        meses_pares = [(1, "ENERO"), (2, "FEBRERO"), (3, "MARZO"), (4, "ABRIL"), (5, "MAYO"), (6, "JUNIO"), (7, "JULIO")]

        # Extraemos el año de inicio de la fecha_inicio (ej. "2025-08-18" -> 2025)
        anio_base = datetime.strptime(data["fecha_inicio"], "%Y-%m-%d").year

        for sem in range(1, 7):
            # Calculamos el año según el semestre
            # Sem 1-2: año_base | Sem 3-4: año_base + 1 | Sem 5-6: año_base + 2
            ajuste_anio = (sem - 1) // 2 
            anio_pago = anio_base + ajuste_anio

            # Agregar Inscripción
            db.session.add(EstructuraPago(
                id_generacion=nueva_gen.id_generacion, 
                tipo='INSCRIPCION', 
                semestre=sem,
                concepto=f'INSCRIPCIÓN {sem}° SEM', 
                monto=3000
            ))

            # Agregar Mensualidades
            meses_a_usar = meses_pares if sem % 2 == 0 else meses_impares
            for numero_mes, nombre_mes in meses_a_usar:
                # Ajuste extra: Si el semestre es par (Enero-Julio), el año ya avanzó
                anio_real = anio_pago if sem % 2 != 0 else anio_pago + 1
                
                db.session.add(EstructuraPago(
                    id_generacion=nueva_gen.id_generacion, 
                    tipo='MENSUALIDAD', 
                    semestre=sem,
                    concepto=f'{nombre_mes} - {sem}° SEM', 
                    monto=1500,
                    mes=numero_mes,      
                    anio=anio_real   
                ))

        db.session.commit()
        
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVA_GENERACION",
            descripcion=f"Creó la generación '{nueva_gen.nombre}' y autogeneró esquema de cobros."
        )

        return jsonify({"message": "Generación y esquema de pagos creados exitosamente"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# 📋 LISTAR GENERACIONES 
# ==========================
@catalogo_bp.route("/generaciones", methods=["GET", "OPTIONS"])
def listar_generaciones():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    generaciones = Generacion.query.all()
    resultado = []
    
    for g in generaciones:
        activos = sum(1 for a in g.alumnos if a.estatus == 'ACTIVO')
        bajas = sum(1 for a in g.alumnos if a.estatus in ['BAJA', 'SUSPENDIDO'])
        
        fecha_ini_str = g.fecha_inicio.strftime("%Y-%m-%d") if g.fecha_inicio else ""
        fecha_fin_str = g.fecha_fin.strftime("%Y-%m-%d") if g.fecha_fin else ""
        
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": fecha_ini_str,  
            "fecha_fin": fecha_fin_str,    
            "estado": g.estado,
            "activos": activos, 
            "bajas": bajas
        })
    return jsonify(resultado), 200

# ==========================
# ✏️ ACTUALIZAR GENERACION (Con Automatización Mágica)
# ==========================
@catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["PUT", "OPTIONS"])
def actualizar_generacion(id_generacion):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para editar generaciones"}), 403

    data = request.get_json()
    
    generacion = Generacion.query.get(id_generacion)
    if not generacion:
        return jsonify({"error": "Generación no encontrada"}), 404

    try:
        nombre_anterior = generacion.nombre
        estado_anterior = generacion.estado

        if "nombre" in data: generacion.nombre = data["nombre"]
        if "fecha_inicio" in data: generacion.fecha_inicio = data["fecha_inicio"]
        if "fecha_fin" in data: generacion.fecha_fin = data["fecha_fin"]
        
        # 🔥 AQUÍ EMPIEZA LA MAGIA DE LOS ALUMNOS 🔥
        if "estado" in data: 
            nuevo_estado = data["estado"]
            generacion.estado = nuevo_estado

            # Si estamos CERRANDO la generación...
            if nuevo_estado == 'CERRADA' and estado_anterior == 'ACTIVA':
                alumnos_activos = Alumno.query.filter_by(id_generacion=id_generacion, estatus='ACTIVO').all()
                for alumno in alumnos_activos:
                    alumno.estatus = 'EGRESADO'
                
                mensaje_bitacora = f"Cerró la generación '{nombre_anterior}' y graduó automáticamente a {len(alumnos_activos)} alumnos."

            # Si la REABRIMOS por error...
            elif nuevo_estado == 'ACTIVA' and estado_anterior == 'CERRADA':
                alumnos_egresados = Alumno.query.filter_by(id_generacion=id_generacion, estatus='EGRESADO').all()
                for alumno in alumnos_egresados:
                    alumno.estatus = 'ACTIVO'
                
                mensaje_bitacora = f"Reabrió la generación '{nombre_anterior}' y regresó a {len(alumnos_egresados)} alumnos a estatus Activo."
            
            else:
                mensaje_bitacora = f"Actualizó la configuración de la generación '{nombre_anterior}'."
        else:
            mensaje_bitacora = f"Actualizó datos básicos de la generación '{nombre_anterior}'."

        db.session.commit()

        # 📸 BITÁCORA: Registrar la acción
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_GENERACION",
            descripcion=mensaje_bitacora
        )

        return jsonify({"message": "Generación actualizada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# MÓDULO DE GRUPOS
# ==========================
@catalogo_bp.route("/grupos", methods=["POST", "OPTIONS"])
def registrar_grupo():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para crear grupos"}), 403

    data = request.get_json()
    
    try:
        id_gen = int(data["id_generacion"])
        nombre = data["nombre_grupo"].upper() 

        existe = Grupo.query.filter_by(nombre_grupo=nombre, id_generacion=id_gen).first()
        
        if existe:
            return jsonify({
                "error": f"El Grupo {nombre} ya está registrado para esta generación."
            }), 400

        nuevo_grupo = Grupo(
            nombre_grupo=nombre,
            turno=data.get("turno", "Vespertino"), 
            id_generacion=id_gen
        )
        db.session.add(nuevo_grupo)
        db.session.commit()

        # 📸 BITÁCORA: Crear Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_GRUPO",
            descripcion=f"Creó el grupo '{nombre}' en la Generación ID: {id_gen}"
        )

        return jsonify({"message": "Grupo creado exitosamente"}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# ==========================
# 📋 LISTAR GRUPOS
# ==========================
@catalogo_bp.route("/grupos", methods=["GET", "OPTIONS"])
def listar_grupos():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

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
            "total_alumnos": activos,
            "estado": getattr(g, 'estado', 'ACTIVO') 
        })
    return jsonify(resultado), 200

# ==========================
# ✏️ ACTUALIZAR GRUPO
# ==========================
@catalogo_bp.route("/grupos/<int:id_grupo>", methods=["PUT", "OPTIONS"])
def actualizar_grupo(id_grupo):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para editar grupos"}), 403

    data = request.get_json()
    grupo = Grupo.query.get(id_grupo)
    
    if not grupo:
        return jsonify({"error": "Grupo no encontrado"}), 404
    
    try:
        nombre_anterior = grupo.nombre_grupo
        nuevo_nombre = data.get("nombre_grupo", grupo.nombre_grupo).upper()
        nueva_gen = int(data.get("id_generacion", grupo.id_generacion))

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

        # 📸 BITÁCORA: Editar Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_GRUPO",
            descripcion=f"Modificó el grupo '{nombre_anterior}'. Nuevo nombre: '{nuevo_nombre}', Turno: '{grupo.turno}'"
        )

        return jsonify({"message": "Grupo actualizado correctamente"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🗑️ ELIMINAR UN GRUPO PERMANENTEMENTE
# ==========================================
@catalogo_bp.route("/grupos/<int:id_grupo>", methods=["DELETE", "OPTIONS"])
def eliminar_grupo(id_grupo):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL (SOLO SISTEMAS)
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede eliminar grupos físicamente"}), 403

    try:
        grupo = Grupo.query.get(id_grupo)
        if not grupo: 
            return jsonify({"error": "Grupo no encontrado"}), 404

        # 🛡️ REGLA DE ORO: No borrar si hay alumnos adentro
        alumnos_en_grupo = Alumno.query.filter_by(id_grupo=id_grupo).count()
        if alumnos_en_grupo > 0:
            return jsonify({"error": f"No puedes eliminar este grupo porque tiene {alumnos_en_grupo} alumnos inscritos. Elimina o mueve los alumnos primero."}), 400

        nombre_grupo = grupo.nombre_grupo
        db.session.delete(grupo)
        db.session.commit()

        # 📸 BITÁCORA: Eliminar Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_GRUPO",
            descripcion=f"Eliminó permanentemente el Grupo {nombre_grupo} (ID: {id_grupo})"
        )

        return jsonify({"message": "Grupo eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "No se puede eliminar porque este grupo ya tiene registros o historial asociado en el sistema."}), 500
    
# ==========================
# 🗑️ ELIMINAR GENERACIÓN
# ==========================
@catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["DELETE", "OPTIONS"])
def eliminar_generacion(id_generacion):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL (SOLO SISTEMAS)
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede eliminar generaciones físicamente"}), 403

    try:
        generacion = Generacion.query.get(id_generacion)
        if not generacion:
            return jsonify({"error": "Generación no encontrada"}), 404

        # 🛡️ REGLA DE ORO: No borrar si hay alumnos o grupos
        alumnos_count = Alumno.query.filter_by(id_generacion=id_generacion).count()
        grupos_count = Grupo.query.filter_by(id_generacion=id_generacion).count()

        if alumnos_count > 0 or grupos_count > 0:
            return jsonify({
                "error": f"No se puede eliminar: Esta generación tiene {grupos_count} grupos y {alumnos_count} alumnos vinculados. Mejor cierra el ciclo."
            }), 400

        nombre_gen = generacion.nombre
        db.session.delete(generacion)
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_GENERACION",
            descripcion=f"Eliminó permanentemente la generación '{nombre_gen}'"
        )

        return jsonify({"message": "Generación eliminada correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

""" from flask import Blueprint, request, jsonify
from extensions import db
from models import Generacion, Grupo, EstructuraPago, Alumno
from datetime import datetime
import re
# 📸 IMPORTAMOS LAS HERRAMIENTAS DE BITÁCORA
from helpers import registrar_accion, obtener_id_admin

catalogo_bp = Blueprint('catalogo_bp', __name__)

# ==========================
# ✅ MÓDULO DE GENERACIONES (Con Plantillas Nativas Inteligentes)
# ==========================
@catalogo_bp.route("/generaciones", methods=["POST"])
def registrar_generacion():
    data = request.get_json()
    nombre_gen = data["nombre"].strip()
    
    try:
        # 🛡️ VALIDACIÓN: ¿Ya existe esta generación?
        existe = Generacion.query.filter_by(nombre=nombre_gen).first()
        if existe:
            return jsonify({"error": f"La generación '{nombre_gen}' ya existe."}), 400

        nueva_gen = Generacion(
            nombre=nombre_gen,
            fecha_inicio=data["fecha_inicio"],
            fecha_fin=data["fecha_fin"],
            estado=data.get("estado", "ACTIVA")
        )
        db.session.add(nueva_gen)
        db.session.flush() 

        # 🧠 LÓGICA DE PAGOS MEJORADA
        meses_impares = [(8, "AGOSTO"), (9, "SEPTIEMBRE"), (10, "OCTUBRE"), (11, "NOVIEMBRE"), (12, "DICIEMBRE")]
        meses_pares = [(1, "ENERO"), (2, "FEBRERO"), (3, "MARZO"), (4, "ABRIL"), (5, "MAYO"), (6, "JUNIO"), (7, "JULIO")]

        # Extraemos el año de inicio de la fecha_inicio (ej. "2025-08-18" -> 2025)
        anio_base = datetime.strptime(data["fecha_inicio"], "%Y-%m-%d").year

        for sem in range(1, 7):
            # Calculamos el año según el semestre
            # Sem 1-2: año_base | Sem 3-4: año_base + 1 | Sem 5-6: año_base + 2
            ajuste_anio = (sem - 1) // 2 
            anio_pago = anio_base + ajuste_anio

            # Agregar Inscripción
            db.session.add(EstructuraPago(
                id_generacion=nueva_gen.id_generacion, 
                tipo='INSCRIPCION', 
                semestre=sem,
                concepto=f'INSCRIPCIÓN {sem}° SEM', 
                monto=3000
            ))

            # Agregar Mensualidades
            meses_a_usar = meses_pares if sem % 2 == 0 else meses_impares
            for numero_mes, nombre_mes in meses_a_usar:
                # Ajuste extra: Si el semestre es par (Enero-Julio), el año ya avanzó
                anio_real = anio_pago if sem % 2 != 0 else anio_pago + 1
                
                db.session.add(EstructuraPago(
                    id_generacion=nueva_gen.id_generacion, 
                    tipo='MENSUALIDAD', 
                    semestre=sem,
                    concepto=f'{nombre_mes} - {sem}° SEM', 
                    monto=1500,
                    mes=numero_mes,      
                    anio=anio_real   
                ))

        db.session.commit()
        
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVA_GENERACION",
            descripcion=f"Creó la generación '{nueva_gen.nombre}' y autogeneró esquema de cobros."
        )

        return jsonify({"message": "Generación y esquema de pagos creados exitosamente"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# 📋 LISTAR GENERACIONES 
# ==========================
@catalogo_bp.route("/generaciones", methods=["GET", "OPTIONS"])
def listar_generaciones():
    if request.method == "OPTIONS": return jsonify({}), 200
    generaciones = Generacion.query.all()
    resultado = []
    
    for g in generaciones:
        activos = sum(1 for a in g.alumnos if a.estatus == 'ACTIVO')
        bajas = sum(1 for a in g.alumnos if a.estatus in ['BAJA', 'SUSPENDIDO'])
        
        fecha_ini_str = g.fecha_inicio.strftime("%Y-%m-%d") if g.fecha_inicio else ""
        fecha_fin_str = g.fecha_fin.strftime("%Y-%m-%d") if g.fecha_fin else ""
        
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": fecha_ini_str,  
            "fecha_fin": fecha_fin_str,    
            "estado": g.estado,
            "activos": activos, 
            "bajas": bajas
        })
    return jsonify(resultado), 200

# ==========================
# ✏️ ACTUALIZAR GENERACION (Con Automatización Mágica)
# ==========================
@catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["PUT"])
def actualizar_generacion(id_generacion):
    data = request.get_json()
    
    generacion = Generacion.query.get(id_generacion)
    if not generacion:
        return jsonify({"error": "Generación no encontrada"}), 404

    try:
        nombre_anterior = generacion.nombre
        estado_anterior = generacion.estado

        if "nombre" in data: generacion.nombre = data["nombre"]
        if "fecha_inicio" in data: generacion.fecha_inicio = data["fecha_inicio"]
        if "fecha_fin" in data: generacion.fecha_fin = data["fecha_fin"]
        
        # 🔥 AQUÍ EMPIEZA LA MAGIA DE LOS ALUMNOS 🔥
        if "estado" in data: 
            nuevo_estado = data["estado"]
            generacion.estado = nuevo_estado

            # Si estamos CERRANDO la generación...
            if nuevo_estado == 'CERRADA' and estado_anterior == 'ACTIVA':
                alumnos_activos = Alumno.query.filter_by(id_generacion=id_generacion, estatus='ACTIVO').all()
                for alumno in alumnos_activos:
                    alumno.estatus = 'EGRESADO'
                
                mensaje_bitacora = f"Cerró la generación '{nombre_anterior}' y graduó automáticamente a {len(alumnos_activos)} alumnos."

            # Si la REABRIMOS por error...
            elif nuevo_estado == 'ACTIVA' and estado_anterior == 'CERRADA':
                alumnos_egresados = Alumno.query.filter_by(id_generacion=id_generacion, estatus='EGRESADO').all()
                for alumno in alumnos_egresados:
                    alumno.estatus = 'ACTIVO'
                
                mensaje_bitacora = f"Reabrió la generación '{nombre_anterior}' y regresó a {len(alumnos_egresados)} alumnos a estatus Activo."
            
            else:
                mensaje_bitacora = f"Actualizó la configuración de la generación '{nombre_anterior}'."
        else:
            mensaje_bitacora = f"Actualizó datos básicos de la generación '{nombre_anterior}'."

        db.session.commit()

        # 📸 BITÁCORA: Registrar la acción
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_GENERACION",
            descripcion=mensaje_bitacora
        )

        return jsonify({"message": "Generación actualizada correctamente"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================
# MÓDULO DE GRUPOS
# ==========================
@catalogo_bp.route("/grupos", methods=["POST"])
def registrar_grupo():
    data = request.get_json()
    
    try:
        id_gen = int(data["id_generacion"])
        nombre = data["nombre_grupo"].upper() 

        existe = Grupo.query.filter_by(nombre_grupo=nombre, id_generacion=id_gen).first()
        
        if existe:
            return jsonify({
                "error": f"El Grupo {nombre} ya está registrado para esta generación."
            }), 400

        nuevo_grupo = Grupo(
            nombre_grupo=nombre,
            turno=data.get("turno", "Vespertino"), 
            id_generacion=id_gen
        )
        db.session.add(nuevo_grupo)
        db.session.commit()

        # 📸 BITÁCORA: Crear Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_GRUPO",
            descripcion=f"Creó el grupo '{nombre}' en la Generación ID: {id_gen}"
        )

        return jsonify({"message": "Grupo creado exitosamente"}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# ==========================
# 📋 LISTAR GRUPOS
# ==========================
@catalogo_bp.route("/grupos", methods=["GET"])
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
            "total_alumnos": activos,
            "estado": getattr(g, 'estado', 'ACTIVO') 
        })
    return jsonify(resultado), 200

# ==========================
# ✏️ ACTUALIZAR GRUPO
# ==========================
@catalogo_bp.route("/grupos/<int:id_grupo>", methods=["PUT"])
def actualizar_grupo(id_grupo):
    data = request.get_json()
    grupo = Grupo.query.get(id_grupo)
    
    if not grupo:
        return jsonify({"error": "Grupo no encontrado"}), 404
    
    try:
        nombre_anterior = grupo.nombre_grupo
        nuevo_nombre = data.get("nombre_grupo", grupo.nombre_grupo).upper()
        nueva_gen = int(data.get("id_generacion", grupo.id_generacion))

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

        # 📸 BITÁCORA: Editar Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_GRUPO",
            descripcion=f"Modificó el grupo '{nombre_anterior}'. Nuevo nombre: '{nuevo_nombre}', Turno: '{grupo.turno}'"
        )

        return jsonify({"message": "Grupo actualizado correctamente"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🗑️ ELIMINAR UN GRUPO PERMANENTEMENTE
# ==========================================
@catalogo_bp.route("/grupos/<int:id_grupo>", methods=["DELETE", "OPTIONS"])
def eliminar_grupo(id_grupo):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        grupo = Grupo.query.get(id_grupo)
        if not grupo: 
            return jsonify({"error": "Grupo no encontrado"}), 404

        # 🛡️ REGLA DE ORO: No borrar si hay alumnos adentro
        alumnos_en_grupo = Alumno.query.filter_by(id_grupo=id_grupo).count()
        if alumnos_en_grupo > 0:
            return jsonify({"error": f"No puedes eliminar este grupo porque tiene {alumnos_en_grupo} alumnos inscritos. Elimina o mueve los alumnos primero."}), 400

        nombre_grupo = grupo.nombre_grupo
        db.session.delete(grupo)
        db.session.commit()

        # 📸 BITÁCORA: Eliminar Grupo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_GRUPO",
            descripcion=f"Eliminó permanentemente el Grupo {nombre_grupo} (ID: {id_grupo})"
        )

        return jsonify({"message": "Grupo eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "No se puede eliminar porque este grupo ya tiene registros o historial asociado en el sistema."}), 500
    
# ==========================
# 🗑️ ELIMINAR GENERACIÓN
# ==========================
@catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["DELETE", "OPTIONS"])
def eliminar_generacion(id_generacion):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        generacion = Generacion.query.get(id_generacion)
        if not generacion:
            return jsonify({"error": "Generación no encontrada"}), 404

        # 🛡️ REGLA DE ORO: No borrar si hay alumnos o grupos
        alumnos_count = Alumno.query.filter_by(id_generacion=id_generacion).count()
        grupos_count = Grupo.query.filter_by(id_generacion=id_generacion).count()

        if alumnos_count > 0 or grupos_count > 0:
            return jsonify({
                "error": f"No se puede eliminar: Esta generación tiene {grupos_count} grupos y {alumnos_count} alumnos vinculados. Mejor cierra el ciclo."
            }), 400

        nombre_gen = generacion.nombre
        db.session.delete(generacion)
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_GENERACION",
            descripcion=f"Eliminó permanentemente la generación '{nombre_gen}'"
        )

        return jsonify({"message": "Generación eliminada correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 """