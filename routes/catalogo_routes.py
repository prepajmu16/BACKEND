from flask import Blueprint, request, jsonify
from extensions import db
from models import Generacion, Grupo, EstructuraPago
from datetime import datetime
import re

catalogo_bp = Blueprint('catalogo_bp', __name__)

# Pega aquí exactamente tus funciones:
# @catalogo_bp.route("/generaciones", methods=["POST"]) def registrar_generacion(): ...
# ==========================
# ✅ MÓDULO DE GENERACIONES (Con Plantillas Nativas Inteligentes)
# ==========================
@catalogo_bp.route("/generaciones", methods=["POST"])
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

        # 🧠 DICCIONARIOS DE CALENDARIO ESCOLAR EXPERTO
        meses_impares = [
            (8, "AGOSTO"), (9, "SEPTIEMBRE"), (10, "OCTUBRE"), 
            (11, "NOVIEMBRE"), (12, "DICIEMBRE")
        ]
        
        meses_pares = [
            (1, "ENERO"), (2, "FEBRERO"), (3, "MARZO"), (4, "ABRIL"), 
            (5, "MAYO"), (6, "JUNIO"), (7, "JULIO")
        ]

        # Tomamos el año actual para ponérselo al molde
        anio_creacion = datetime.now().year

        for sem in range(1, 7):
            # 1. Creamos la Inscripción (El molde base)
            db.session.add(EstructuraPago(
                id_generacion=nueva_gen.id_generacion, 
                tipo='INSCRIPCION', 
                semestre=sem,
                concepto=f'INSCRIPCIÓN {sem}° SEM', 
                monto=3000
            ))

            # 2. Creamos las mensualidades con Inteligencia Nativa
            meses_a_usar = meses_pares if sem % 2 == 0 else meses_impares
            
            for numero_mes, nombre_mes in meses_a_usar:
                db.session.add(EstructuraPago(
                    id_generacion=nueva_gen.id_generacion, 
                    tipo='MENSUALIDAD', 
                    semestre=sem,
                    concepto=f'{nombre_mes} - {sem}° SEM', 
                    monto=1500,
                    mes=numero_mes,      # 🔥 ESTA ES LA CLAVE PARA EL SEMÁFORO
                    anio=anio_creacion   # 🔥 Y ESTA TAMBIÉN
                ))

        db.session.commit()
        return jsonify({"message": "Generación y esquema de pagos creados con inteligencia"}), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
# @catalogo_bp.route("/generaciones", methods=["GET", "OPTIONS"]) def listar_generaciones(): ...
# ==========================
# 📋 LISTAR GENERACIONES (A prueba de fechas nulas)
# ==========================
@catalogo_bp.route("/generaciones", methods=["GET", "OPTIONS"])
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
# @catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["PUT"]) def actualizar_generacion(): ...
# ✅ Ruta PUT para editar y cambiar estado ("Apagar" Generación)
@catalogo_bp.route("/generaciones/<int:id_generacion>", methods=["PUT"])
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
# @catalogo_bp.route("/grupos", methods=["POST"]) def registrar_grupo(): ...
# ==========================
# MÓDULO DE GRUPOS
# ==========================
@catalogo_bp.route("/grupos", methods=["POST"])
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
    



# @catalogo_bp.route("/grupos", methods=["GET"]) def listar_grupos(): ...
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
            "total_alumnos": activos
        })
    return jsonify(resultado), 200

# @catalogo_bp.route("/grupos/<int:id_grupo>", methods=["PUT"]) def actualizar_grupo(): ...
@catalogo_bp.route("/grupos/<int:id_grupo>", methods=["PUT"])
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