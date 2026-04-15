from flask import Blueprint, request, jsonify
from extensions import db
from models import Pago, EstructuraPago, Alumno
from datetime import datetime
from helpers import registrar_accion, obtener_id_admin
# 🛡️ IMPORTAMOS EL ESCUDO DE SEGURIDAD
from flask_jwt_extended import verify_jwt_in_request, get_jwt

caja_bp = Blueprint('caja_bp', __name__)

# ==========================================
# 💰 MÓDULO FINANCIERO: ESTRUCTURA DE PAGOS
# ==========================================
@caja_bp.route("/estructura-pagos/<int:id_generacion>", methods=["GET", "OPTIONS"])
def obtener_estructura(id_generacion):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
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

@caja_bp.route("/estructura-pagos", methods=["POST", "OPTIONS"])
def crear_concepto():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para crear conceptos de pago"}), 403

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
        
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_CONCEPTO_PAGO",
            descripcion=f"Agregó el concepto {nuevo_concepto.concepto} (${nuevo_concepto.monto}) a la Generación {data['id_generacion']}"
        )

        return jsonify({"message": "Concepto de pago creado exitosamente"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@caja_bp.route("/estructura-pagos/<int:id_estructura>", methods=["DELETE", "OPTIONS"])
def eliminar_concepto(id_estructura):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL (SOLO SISTEMAS)
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede eliminar conceptos de pago"}), 403

    concepto = EstructuraPago.query.get(id_estructura)
    if not concepto:
        return jsonify({"error": "Concepto no encontrado"}), 404
        
    try:
        nombre_concepto = concepto.concepto
        db.session.delete(concepto)
        db.session.commit()
        
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_CONCEPTO_PAGO",
            descripcion=f"Eliminó el concepto {nombre_concepto} (ID: {id_estructura})"
        )

        return jsonify({"message": "Concepto eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "No se puede eliminar porque ya hay recibos cobrados con este concepto."}), 500    

# ==========================================
# 💵 MÓDULO DE CAJA (PUNTO DE COBRO)
# ==========================================
@caja_bp.route("/caja/deudas/<string:matricula>", methods=["GET", "OPTIONS"])
def obtener_deudas(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404

        todos_los_pagos = Pago.query.filter_by(id_alumno=alumno.id_alumno).all()
        pagos_pendientes = [p for p in todos_los_pagos if str(getattr(p, 'estado', getattr(p, 'estatus_pago', ''))).upper() in ['PENDIENTE', 'PARCIAL']]
        
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
@caja_bp.route("/caja/alumnos", methods=["GET", "OPTIONS"])
def obtener_alumnos_caja():
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    id_gen = request.args.get('generacion')
    ahora = datetime.now()

    try:
        if id_gen and id_gen != '0':
            alumnos = Alumno.query.filter_by(id_generacion=id_gen).all()
        else:
            alumnos = Alumno.query.all()

        resultado = []
        
        for a in alumnos:
            estatus_alumno = getattr(a, 'estatus', 'ACTIVO')
            semestre_actual_alumno = getattr(a, 'semestre_actual', 1) or 1
            
            fecha_limite = ahora.date()
            if estatus_alumno == 'BAJA' and getattr(a, 'fecha_baja', None):
                fecha_limite = a.fecha_baja
                
            limite_anio = fecha_limite.year
            limite_mes = fecha_limite.month

            pagos_del_alumno = db.session.query(Pago, EstructuraPago).join(
                EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
            ).filter(Pago.id_alumno == a.id_alumno).all()
            
            m_pendientes = 0
            eee_pendientes = 0
            
            for p, e in pagos_del_alumno:
                estado_pago = str(getattr(p, 'estatus_pago', getattr(p, 'estado', ''))).upper()
                
                if estado_pago in ['PENDIENTE', 'PARCIAL']:
                    tipo_est = str(e.tipo).upper()
                    
                    cobro_anio = None
                    cobro_mes = None
                    
                    if hasattr(e, 'anio') and e.anio:
                        cobro_anio = int(e.anio)
                        cobro_mes = int(getattr(e, 'mes', 1))
                    elif hasattr(e, 'fecha_vencimiento') and e.fecha_vencimiento:
                        if isinstance(e.fecha_vencimiento, str):
                            try:
                                dt = datetime.strptime(e.fecha_vencimiento, "%Y-%m-%d")
                                cobro_anio = dt.year
                                cobro_mes = dt.month
                            except: pass
                        else:
                            cobro_anio = e.fecha_vencimiento.year
                            cobro_mes = e.fecha_vencimiento.month
                    
                    es_deuda_real = False

                    if cobro_anio and cobro_mes:
                        if cobro_anio < limite_anio:
                            es_deuda_real = True
                        elif cobro_anio == limite_anio:
                            if cobro_mes < limite_mes:
                                es_deuda_real = True
                            elif cobro_mes == limite_mes:
                                if ahora.day > 5:
                                    es_deuda_real = True
                    else:
                        semestre_cobro = getattr(e, 'semestre', 1) or 1
                        if semestre_cobro <= semestre_actual_alumno and estatus_alumno != 'BAJA':
                            es_deuda_real = True 
                    
                    if es_deuda_real:
                        if 'MENSUALIDAD' in tipo_est:
                            m_pendientes += 1
                        else:
                            eee_pendientes += 1

            nombre_del_grupo = a.grupo.nombre_grupo if a.grupo else "S/G"

            resultado.append({
                "nombre": f"{a.apellido} {a.nombre}".upper(),
                "matricula": a.matricula,
                "generacion_id": a.id_generacion,
                "grupo": nombre_del_grupo,
                "estatus": estatus_alumno,
                "semestre_actual": semestre_actual_alumno,
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
    
# ==========================================
# 📊 API: OBTENER HISTORIAL DE PAGOS
# ==========================================
@caja_bp.route("/caja/historial/<string:matricula>", methods=["GET", "OPTIONS"])
def historial_pagos(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN', 'LECTURA']:
        return jsonify({"error": "Acceso denegado"}), 403

    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

        historial = db.session.query(Pago, EstructuraPago).filter(
            Pago.id_estructura == EstructuraPago.id_estructura, Pago.id_alumno == alumno.id_alumno
        ).order_by(EstructuraPago.anio.asc(), EstructuraPago.mes.asc()).all()
        
        resultado = []
        for p, e in historial:
            categoria_str = e.tipo.value if hasattr(e.tipo, 'value') else str(e.tipo)
            estado_str = p.estado.value if hasattr(p.estado, 'value') else str(getattr(p, 'estado', getattr(p, 'estatus_pago', '')))
            
            fecha_formateada = p.fecha_pago.strftime("%d/%m/%Y") if p.fecha_pago else None
            fecha_raw = p.fecha_pago.strftime("%Y-%m-%d") if p.fecha_pago else None

            monto_total = float(e.monto) if e.monto is not None else 0.0
            monto_abonado = float(getattr(p, 'monto_abonado', 0.0) or 0.0)

            resultado.append({
                "id": p.id_pago, 
                "concepto": e.concepto, 
                "monto": monto_total,
                "monto_abonado": monto_abonado,
                "restante": monto_total - monto_abonado, 
                "semestre": e.semestre, 
                "categoria": categoria_str.split('.')[-1], 
                "pagado": estado_str.split('.')[-1] == 'PAGADO',
                "es_parcial": estado_str.split('.')[-1] == 'PARCIAL',
                "fecha_pago": fecha_formateada, 
                "fecha_raw": fecha_raw, 
                "folio": p.folio,
                "mes": getattr(e, 'mes', None),
                "anio": getattr(e, 'anio', None)
            })
        return jsonify(resultado), 200
    except Exception as err:
        return jsonify({"error": str(err)}), 500

# ==========================================
# 🔄 API: REVERTIR PAGO (APAGAR BOTÓN)
# ==========================================
@caja_bp.route("/caja/revertir/<int:id_pago>", methods=["PUT", "OPTIONS"])
def revertir_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para revertir pagos"}), 403

    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404

        if hasattr(pago, 'estatus_pago'): pago.estatus_pago = 'PENDIENTE'
        else: pago.estado = 'PENDIENTE'
        
        fecha_borrada = pago.fecha_pago
        folio_borrado = pago.folio
        monto_borrado = getattr(pago, 'monto_abonado', 0.0)

        pago.fecha_pago = None
        pago.folio = None
        if hasattr(pago, 'monto_abonado'): pago.monto_abonado = 0.0 

        estructura = EstructuraPago.query.get(pago.id_estructura)
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="REVERTIR_PAGO",
            descripcion=f"Canceló el cobro de '{estructura.concepto}' (${monto_borrado}). Folio borrado: {folio_borrado}"
        )

        return jsonify({"message": "Pago cancelado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 💸 API: REGISTRAR UN PAGO FÍSICO 
# ==========================================
@caja_bp.route("/caja/registrar", methods=["POST", "OPTIONS"])
def registrar_cobro_oficial():
    if request.method == "OPTIONS": return jsonify({}), 200
        
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para registrar cobros"}), 403

    data = request.get_json()
    id_pago = data.get("id_pago")
    fecha_ingresada = data.get("fecha")
    folio_ingresado = data.get("folio")
    
    monto_recibido = float(data.get("monto_recibido", 0))

    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Recibo no encontrado"}), 404
        
        estructura = EstructuraPago.query.get(pago.id_estructura)
        costo_total = float(estructura.monto)
        
        abonado_historico = float(getattr(pago, 'monto_abonado', 0.0) or 0.0)
        nuevo_acumulado = abonado_historico + monto_recibido
        
        if nuevo_acumulado >= costo_total:
            estado_nuevo = 'PAGADO'
            if hasattr(pago, 'monto_abonado'): pago.monto_abonado = costo_total
        else:
            estado_nuevo = 'PARCIAL'
            if hasattr(pago, 'monto_abonado'): pago.monto_abonado = nuevo_acumulado

        if hasattr(pago, 'estatus_pago'): pago.estatus_pago = estado_nuevo
        else: pago.estado = estado_nuevo
            
        pago.fecha_pago = fecha_ingresada 
        
        etiqueta_nuevo_folio = f"{folio_ingresado}(${monto_recibido:g})"

        if pago.folio and pago.folio.strip() != "":
            pago.folio = f"{pago.folio} y {etiqueta_nuevo_folio}"
        else:
            pago.folio = etiqueta_nuevo_folio
        
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="COBRO_REALIZADO",
            descripcion=f"Cobró ${monto_recibido} por '{estructura.concepto}'. Folio: {folio_ingresado}. Estatus: {estado_nuevo}"
        )

        return jsonify({"message": f"Cobro exitoso. Estatus: {estado_nuevo}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# ➕ API: CREAR UN COBRO DESDE EL MODAL
# ==========================================
@caja_bp.route("/caja/crear", methods=["POST", "OPTIONS"])
def crear_pago_manual():
    if request.method == "OPTIONS": return jsonify({}), 200

    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para crear cargos manuales"}), 403

    data = request.get_json()
    try:
        alumno = Alumno.query.filter_by(matricula=data['matricula']).first()
        if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404
        
        tipo_recibido = data.get('categoria') or data.get('tipo')
        if not tipo_recibido: return jsonify({"error": "Falta el tipo de cobro"}), 400

        ahora = datetime.now()
        nueva_estructura = EstructuraPago(
            id_generacion=alumno.id_generacion,
            tipo=tipo_recibido,
            semestre=data.get('semestre', 1),
            concepto=data['concepto'].upper(),
            monto=data['monto'],
            mes=data.get('mes', ahora.month), 
            anio=data.get('anio', ahora.year) 
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
        
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_CARGO_MANUAL",
            descripcion=f"Creó un cargo manual por '{nueva_estructura.concepto}' (${nueva_estructura.monto}) al alumno {alumno.matricula}"
        )

        return jsonify({"message": "Cobro registrado correctamente"}), 201
    except Exception as err:
        db.session.rollback()
        return jsonify({"error": str(err)}), 500

# ==========================================
# ✏️ API: EDITAR CUALQUIER DATO DE UN COBRO
# ==========================================
@caja_bp.route("/caja/pago/<int:id_pago>", methods=["PUT", "OPTIONS"])
def editar_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') not in ['SISTEMAS', 'ADMIN']:
        return jsonify({"error": "No tienes permisos para editar cobros"}), 403

    data = request.get_json()
    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404
        
        estructura = EstructuraPago.query.get(pago.id_estructura)
        concepto_anterior = estructura.concepto if estructura else "Desconocido"
        
        if estructura:
            estructura.concepto = data.get("concepto", estructura.concepto).upper()
            estructura.monto = data.get("monto", estructura.monto)
            
        estado_pago = str(getattr(pago, 'estado', getattr(pago, 'estatus_pago', ''))).upper()
        if estado_pago in ['PAGADO', 'PARCIAL']:
            if "fecha" in data: pago.fecha_pago = data["fecha"]
            if "folio" in data: pago.folio = data["folio"]
            
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_COBRO",
            descripcion=f"Editó el recibo ID {id_pago} ({concepto_anterior})"
        )

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
    
    # 🛡️ VALIDACIÓN DE TOKEN Y ROL (SOLO SISTEMAS)
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Solo el nivel SISTEMAS puede eliminar registros de cobros de la base de datos"}), 403

    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404
        
        db.session.delete(pago)
        db.session.commit()

        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_RECIBO",
            descripcion=f"Eliminó el recibo de cobro ID {id_pago} del sistema"
        )

        return jsonify({"message": "Cobro eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
""" from flask import Blueprint, request, jsonify
from extensions import db
from models import Pago, EstructuraPago, Alumno
from datetime import datetime
# 📸 IMPORTAMOS LAS HERRAMIENTAS DE BITÁCORA
from helpers import registrar_accion, obtener_id_admin

caja_bp = Blueprint('caja_bp', __name__)

# ==========================================
# 💰 MÓDULO FINANCIERO: ESTRUCTURA DE PAGOS
# ==========================================
@caja_bp.route("/estructura-pagos/<int:id_generacion>", methods=["GET"])
def obtener_estructura(id_generacion):
    try:
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
        
        # 📸 BITÁCORA: Nuevo concepto
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_CONCEPTO_PAGO",
            descripcion=f"Agregó el concepto {nuevo_concepto.concepto} (${nuevo_concepto.monto}) a la Generación {data['id_generacion']}"
        )

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
        nombre_concepto = concepto.concepto
        db.session.delete(concepto)
        db.session.commit()
        
        # 📸 BITÁCORA: Eliminar concepto
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_CONCEPTO_PAGO",
            descripcion=f"Eliminó el concepto {nombre_concepto} (ID: {id_estructura})"
        )

        return jsonify({"message": "Concepto eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "No se puede eliminar porque ya hay recibos cobrados con este concepto."}), 500    

# ==========================================
# 💵 MÓDULO DE CAJA (PUNTO DE COBRO)
# ==========================================
@caja_bp.route("/caja/deudas/<string:matricula>", methods=["GET"])
def obtener_deudas(matricula):
    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404

        todos_los_pagos = Pago.query.filter_by(id_alumno=alumno.id_alumno).all()
        pagos_pendientes = [p for p in todos_los_pagos if str(getattr(p, 'estado', getattr(p, 'estatus_pago', ''))).upper() in ['PENDIENTE', 'PARCIAL']]
        
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
@caja_bp.route("/caja/alumnos", methods=["GET"])
def obtener_alumnos_caja():
    id_gen = request.args.get('generacion')
    ahora = datetime.now()

    try:
        if id_gen and id_gen != '0':
            alumnos = Alumno.query.filter_by(id_generacion=id_gen).all()
        else:
            alumnos = Alumno.query.all()

        resultado = []
        
        for a in alumnos:
            estatus_alumno = getattr(a, 'estatus', 'ACTIVO')
            semestre_actual_alumno = getattr(a, 'semestre_actual', 1) or 1
            
            # Límite de tiempo: Hoy (o la fecha de baja si el alumno desertó)
            fecha_limite = ahora.date()
            if estatus_alumno == 'BAJA' and getattr(a, 'fecha_baja', None):
                fecha_limite = a.fecha_baja
                
            limite_anio = fecha_limite.year
            limite_mes = fecha_limite.month

            pagos_del_alumno = db.session.query(Pago, EstructuraPago).join(
                EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
            ).filter(Pago.id_alumno == a.id_alumno).all()
            
            m_pendientes = 0
            eee_pendientes = 0
            
            for p, e in pagos_del_alumno:
                estado_pago = str(getattr(p, 'estatus_pago', getattr(p, 'estado', ''))).upper()
                
                if estado_pago in ['PENDIENTE', 'PARCIAL']:
                    tipo_est = str(e.tipo).upper()
                    
                    cobro_anio = None
                    cobro_mes = None
                    
                    # Extraer fechas si las tiene
                    if hasattr(e, 'anio') and e.anio:
                        cobro_anio = int(e.anio)
                        cobro_mes = int(getattr(e, 'mes', 1))
                    elif hasattr(e, 'fecha_vencimiento') and e.fecha_vencimiento:
                        if isinstance(e.fecha_vencimiento, str):
                            try:
                                dt = datetime.strptime(e.fecha_vencimiento, "%Y-%m-%d")
                                cobro_anio = dt.year
                                cobro_mes = dt.month
                            except: pass
                        else:
                            cobro_anio = e.fecha_vencimiento.year
                            cobro_mes = e.fecha_vencimiento.month
                    
                    es_deuda_real = False

                    # 🔥 NUEVA LÓGICA: LA FECHA MANDA SOBRE EL SEMESTRE 🔥
                    # 1. Si el cobro tiene fecha exacta (Mes y Año), nos guiamos 100% por el calendario
                    if cobro_anio and cobro_mes:
                        if cobro_anio < limite_anio:
                            es_deuda_real = True
                        elif cobro_anio == limite_anio:
                            if cobro_mes < limite_mes:
                                es_deuda_real = True
                            elif cobro_mes == limite_mes:
                                # Tolerancia: Se considera deuda si ya pasó el día 5 del mes
                                if ahora.day > 5:
                                    es_deuda_real = True
                    # 2. Si NO tiene fecha (ej. una Inscripción genérica), entonces sí evaluamos por semestre
                    else:
                        semestre_cobro = getattr(e, 'semestre', 1) or 1
                        if semestre_cobro <= semestre_actual_alumno and estatus_alumno != 'BAJA':
                            es_deuda_real = True 
                    
                    if es_deuda_real:
                        if 'MENSUALIDAD' in tipo_est:
                            m_pendientes += 1
                        else:
                            eee_pendientes += 1

            nombre_del_grupo = a.grupo.nombre_grupo if a.grupo else "S/G"

            resultado.append({
                "nombre": f"{a.apellido} {a.nombre}".upper(),
                "matricula": a.matricula,
                "generacion_id": a.id_generacion,
                "grupo": nombre_del_grupo,
                "estatus": estatus_alumno,
                "semestre_actual": semestre_actual_alumno,
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
    
# ==========================================
# 📊 API: OBTENER HISTORIAL DE PAGOS
# ==========================================
@caja_bp.route("/caja/historial/<string:matricula>", methods=["GET", "OPTIONS"])
def historial_pagos(matricula):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        alumno = Alumno.query.filter_by(matricula=matricula).first()
        if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404

        historial = db.session.query(Pago, EstructuraPago).filter(
            Pago.id_estructura == EstructuraPago.id_estructura, Pago.id_alumno == alumno.id_alumno
        ).order_by(EstructuraPago.anio.asc(), EstructuraPago.mes.asc()).all()
        
        resultado = []
        for p, e in historial:
            categoria_str = e.tipo.value if hasattr(e.tipo, 'value') else str(e.tipo)
            estado_str = p.estado.value if hasattr(p.estado, 'value') else str(getattr(p, 'estado', getattr(p, 'estatus_pago', '')))
            
            fecha_formateada = p.fecha_pago.strftime("%d/%m/%Y") if p.fecha_pago else None
            fecha_raw = p.fecha_pago.strftime("%Y-%m-%d") if p.fecha_pago else None

            monto_total = float(e.monto) if e.monto is not None else 0.0
            monto_abonado = float(getattr(p, 'monto_abonado', 0.0) or 0.0)

            resultado.append({
                "id": p.id_pago, 
                "concepto": e.concepto, 
                "monto": monto_total,
                "monto_abonado": monto_abonado,
                "restante": monto_total - monto_abonado, 
                "semestre": e.semestre, 
                "categoria": categoria_str.split('.')[-1], 
                "pagado": estado_str.split('.')[-1] == 'PAGADO',
                "es_parcial": estado_str.split('.')[-1] == 'PARCIAL',
                "fecha_pago": fecha_formateada, 
                "fecha_raw": fecha_raw, 
                "folio": p.folio,
                "mes": getattr(e, 'mes', None),
                "anio": getattr(e, 'anio', None)
            })
        return jsonify(resultado), 200
    except Exception as err:
        return jsonify({"error": str(err)}), 500

# ==========================================
# 🔄 API: REVERTIR PAGO (APAGAR BOTÓN)
# ==========================================
@caja_bp.route("/caja/revertir/<int:id_pago>", methods=["PUT", "OPTIONS"])
def revertir_pago(id_pago):
    if request.method == "OPTIONS": return jsonify({}), 200
    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Pago no encontrado"}), 404

        if hasattr(pago, 'estatus_pago'): pago.estatus_pago = 'PENDIENTE'
        else: pago.estado = 'PENDIENTE'
        
        fecha_borrada = pago.fecha_pago
        folio_borrado = pago.folio
        monto_borrado = getattr(pago, 'monto_abonado', 0.0)

        pago.fecha_pago = None
        pago.folio = None
        if hasattr(pago, 'monto_abonado'): pago.monto_abonado = 0.0 

        estructura = EstructuraPago.query.get(pago.id_estructura)
        db.session.commit()

        # 📸 BITÁCORA: Revertir pago
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="REVERTIR_PAGO",
            descripcion=f"Canceló el cobro de '{estructura.concepto}' (${monto_borrado}). Folio borrado: {folio_borrado}"
        )

        return jsonify({"message": "Pago cancelado exitosamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 💸 API: REGISTRAR UN PAGO FÍSICO 
# ==========================================
@caja_bp.route("/caja/registrar", methods=["POST", "OPTIONS"])
def registrar_cobro_oficial():
    if request.method == "OPTIONS": return jsonify({}), 200
        
    data = request.get_json()
    id_pago = data.get("id_pago")
    fecha_ingresada = data.get("fecha")
    folio_ingresado = data.get("folio")
    
    monto_recibido = float(data.get("monto_recibido", 0))

    try:
        pago = Pago.query.get(id_pago)
        if not pago: return jsonify({"error": "Recibo no encontrado"}), 404
        
        estructura = EstructuraPago.query.get(pago.id_estructura)
        costo_total = float(estructura.monto)
        
        abonado_historico = float(getattr(pago, 'monto_abonado', 0.0) or 0.0)
        nuevo_acumulado = abonado_historico + monto_recibido
        
        if nuevo_acumulado >= costo_total:
            estado_nuevo = 'PAGADO'
            if hasattr(pago, 'monto_abonado'): pago.monto_abonado = costo_total
        else:
            estado_nuevo = 'PARCIAL'
            if hasattr(pago, 'monto_abonado'): pago.monto_abonado = nuevo_acumulado

        if hasattr(pago, 'estatus_pago'): pago.estatus_pago = estado_nuevo
        else: pago.estado = estado_nuevo
            
        pago.fecha_pago = fecha_ingresada 
        
        etiqueta_nuevo_folio = f"{folio_ingresado}(${monto_recibido:g})"

        if pago.folio and pago.folio.strip() != "":
            pago.folio = f"{pago.folio} y {etiqueta_nuevo_folio}"
        else:
            pago.folio = etiqueta_nuevo_folio
        
        db.session.commit()

        # 📸 BITÁCORA: Registro de Cobro
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="COBRO_REALIZADO",
            descripcion=f"Cobró ${monto_recibido} por '{estructura.concepto}'. Folio: {folio_ingresado}. Estatus: {estado_nuevo}"
        )

        return jsonify({"message": f"Cobro exitoso. Estatus: {estado_nuevo}"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# ➕ API: CREAR UN COBRO DESDE EL MODAL
# ==========================================
@caja_bp.route("/caja/crear", methods=["POST", "OPTIONS"])
def crear_pago_manual():
    if request.method == "OPTIONS": return jsonify({}), 200

    data = request.get_json()
    try:
        alumno = Alumno.query.filter_by(matricula=data['matricula']).first()
        if not alumno: return jsonify({"error": "Alumno no encontrado"}), 404
        
        tipo_recibido = data.get('categoria') or data.get('tipo')
        if not tipo_recibido: return jsonify({"error": "Falta el tipo de cobro"}), 400

        ahora = datetime.now()
        nueva_estructura = EstructuraPago(
            id_generacion=alumno.id_generacion,
            tipo=tipo_recibido,
            semestre=data.get('semestre', 1),
            concepto=data['concepto'].upper(),
            monto=data['monto'],
            mes=data.get('mes', ahora.month), 
            anio=data.get('anio', ahora.year) 
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
        
        # 📸 BITÁCORA: Cargo Manual
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="NUEVO_CARGO_MANUAL",
            descripcion=f"Creó un cargo manual por '{nueva_estructura.concepto}' (${nueva_estructura.monto}) al alumno {alumno.matricula}"
        )

        return jsonify({"message": "Cobro registrado correctamente"}), 201
    except Exception as err:
        db.session.rollback()
        return jsonify({"error": str(err)}), 500

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
        
        estructura = EstructuraPago.query.get(pago.id_estructura)
        concepto_anterior = estructura.concepto if estructura else "Desconocido"
        
        if estructura:
            estructura.concepto = data.get("concepto", estructura.concepto).upper()
            estructura.monto = data.get("monto", estructura.monto)
            
        estado_pago = str(getattr(pago, 'estado', getattr(pago, 'estatus_pago', ''))).upper()
        if estado_pago in ['PAGADO', 'PARCIAL']:
            if "fecha" in data: pago.fecha_pago = data["fecha"]
            if "folio" in data: pago.folio = data["folio"]
            
        db.session.commit()

        # 📸 BITÁCORA: Editar Pago
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="EDITAR_COBRO",
            descripcion=f"Editó el recibo ID {id_pago} ({concepto_anterior})"
        )

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
        
        db.session.delete(pago)
        db.session.commit()

        # 📸 BITÁCORA: Eliminar Recibo
        registrar_accion(
            id_usuario=obtener_id_admin(),
            accion="ELIMINAR_RECIBO",
            descripcion=f"Eliminó el recibo de cobro ID {id_pago} del sistema"
        )

        return jsonify({"message": "Cobro eliminado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500 """