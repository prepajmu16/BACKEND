from flask import Blueprint, request, jsonify
from extensions import db
from models import Pago, EstructuraPago, Alumno
from datetime import datetime # 👈 IMPORTANTE TENER ESTO HASTA ARRIBA


caja_bp = Blueprint('caja_bp', __name__)

# Pega aquí exactamente tus funciones:
# @caja_bp.route("/estructura-pagos...", methods=["GET", "POST", "DELETE"]) ...
# ==========================================
# 💰 MÓDULO FINANCIERO: ESTRUCTURA DE PAGOS
# ==========================================
@caja_bp.route("/estructura-pagos/<int:id_generacion>", methods=["GET"])
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

@caja_bp.route("/estructura-pagos", methods=["POST"])
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

@caja_bp.route("/estructura-pagos/<int:id_estructura>", methods=["DELETE"])
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
# @caja_bp.route("/caja/deudas/<string:matricula>", methods=["GET"]) ...
# ==========================================
# 💵 MÓDULO DE CAJA (PUNTO DE COBRO)
# ==========================================
@caja_bp.route("/caja/deudas/<string:matricula>", methods=["GET"])
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
# @caja_bp.route("/caja/alumnos", methods=["GET"]) ...
# ==========================================
# 💵 MÓDULO DE CAJA: LISTADO DE COBRO Y CAJA
# ==========================================
# ==========================================
# 💵 MÓDULO DE CAJA: LISTADO DE COBRO Y CAJA
# ==========================================
@caja_bp.route("/caja/alumnos", methods=["GET"])
def obtener_alumnos_caja():
    id_gen = request.args.get('generacion')
    if not id_gen or id_gen == '0':
        return jsonify({"error": "Debes seleccionar una generación"}), 400

    ahora = datetime.now()
    mes_actual = ahora.month
    anio_actual = ahora.year

    try:
        alumnos = Alumno.query.filter_by(id_generacion=id_gen).all()
        resultado = []
        
        for a in alumnos:
            # 1. Traemos TODOS los pagos de este alumno
            pagos_del_alumno = db.session.query(Pago, EstructuraPago).join(
                EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
            ).filter(Pago.id_alumno == a.id_alumno).all()
            
            m_pendientes = 0
            eee_pendientes = 0
            
            for p, e in pagos_del_alumno:
                # 2. Verificamos que sea un pago PENDIENTE (Soporta Enums y Strings)
                estado_pago = str(getattr(p, 'estatus_pago', getattr(p, 'estado', ''))).upper()
                
                if 'PENDIENTE' in estado_pago:
                    tipo_est = str(e.tipo).upper()
                    
                    # 3. Si es Extraordinario o EEE, es deuda inmediata
                    if 'EEE' in tipo_est or 'EXT' in tipo_est:
                        eee_pendientes += 1
                    else:
                        # 4. Si es INSCRIPCIÓN o MENSUALIDAD, verificamos la Máquina del Tiempo
                        if e.anio is not None and e.mes is not None:
                            if e.anio < anio_actual:
                                m_pendientes += 1
                            elif e.anio == anio_actual and e.mes <= mes_actual:
                                m_pendientes += 1
                        else:
                            # Fallback: si por alguna razón no tiene fecha, lo contamos
                            m_pendientes += 1

            nombre_del_grupo = a.grupo.nombre_grupo if a.grupo else "S/G"

            resultado.append({
                "nombre": f"{a.nombre} {a.apellido}",
                "matricula": a.matricula,
                "generacion": a.id_generacion,
                "grupo": nombre_del_grupo,
                "tiene_adeudo": (m_pendientes + eee_pendientes) > 0,
                "m_pendientes": m_pendientes,
                "eee_pendientes": eee_pendientes
            })

        return jsonify(resultado), 200
    except Exception as e:
        print("🔴 ERROR EN CAJA ALUMNOS:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
# @caja_bp.route("/caja/historial/<string:matricula>", methods=["GET", "OPTIONS"]) ...
# ==========================================
# 📊 API: OBTENER HISTORIAL DE PAGOS (Ajuste para fecha cruda)
# ==========================================
@caja_bp.route("/caja/historial/<string:matricula>", methods=["GET", "OPTIONS"])
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
                "id": p.id_pago, 
                "concepto": e.concepto, 
                "monto": float(e.monto) if e.monto is not None else 0.0,
                "semestre": e.semestre, 
                "categoria": categoria_str.split('.')[-1], 
                "pagado": estado_str.split('.')[-1] == 'PAGADO',
                "fecha_pago": fecha_formateada, 
                "fecha_raw": fecha_raw, 
                "folio": p.folio,
                # 🔥 AQUÍ AGREGAMOS MES Y AÑO PARA EL SEMÁFORO EN ANGULAR
                "mes": e.mes,
                "anio": e.anio
            })
        return jsonify(resultado), 200
    except Exception as err:
        return jsonify({"error": str(err)}), 500
# @caja_bp.route("/caja/revertir/<int:id_pago>", methods=["PUT", "OPTIONS"]) ...
# ==========================================
# 🔄 API: REVERTIR PAGO (APAGAR BOTÓN)
# ==========================================
@caja_bp.route("/caja/revertir/<int:id_pago>", methods=["PUT", "OPTIONS"])
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
# @caja_bp.route("/caja/registrar", methods=["POST", "OPTIONS"]) ...
# ==========================================
# 💸 API: REGISTRAR UN PAGO FÍSICO (Asentar Folio)
# ==========================================
@caja_bp.route("/caja/registrar", methods=["POST", "OPTIONS"])
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

# @caja_bp.route("/caja/crear", methods=["POST", "OPTIONS"]) ...
# ==========================================
# ➕ API: CREAR UN COBRO DESDE EL MODAL
# ==========================================
@caja_bp.route("/caja/crear", methods=["POST", "OPTIONS"])
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
# @caja_bp.route("/caja/pago/<int:id_pago>", methods=["PUT", "DELETE", "OPTIONS"]) ...
# ==========================================
# ✏️ API: EDITAR CUALQUIER DATO DE UN COBRO
# ==========================================
@caja_bp.route("/caja/pago/<int:id_pago>", methods=["PUT", "OPTIONS"])
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
@caja_bp.route("/caja/pago/<int:id_pago>", methods=["DELETE", "OPTIONS"])
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
    