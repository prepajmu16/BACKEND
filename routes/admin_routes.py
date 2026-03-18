from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from extensions import db
from models import Usuario, Bitacora, Alumno, Generacion, Grupo, Pago, EstructuraPago
from datetime import datetime
import traceback

admin_bp = Blueprint('admin_bp', __name__)

# ==========================================
# 🛠️ FUNCIONES AUXILIARES
# ==========================================
def generar_password_alumno(nombre, apellido, fecha_nacimiento_str):
    """
    Genera una contraseña: 2 letras nombre + 2 letras apellido + 2 dígitos año + 2 dígitos día.
    Ejemplo: Carlos Reyna (2003-05-17) -> CARE0317
    """
    try:
        primer_nombre = nombre.strip().split()[0].upper()
        primer_apellido = apellido.strip().split()[0].upper()
        letras_nom = primer_nombre[:2]
        letras_ape = primer_apellido[:2]
        
        partes_fecha = fecha_nacimiento_str.split('-')
        anio = partes_fecha[0][-2:]
        dia = partes_fecha[2]
        
        return f"{letras_nom}{letras_ape}{anio}{dia}"
    except Exception as e:
        # Respaldo de seguridad por si la fecha viene mal formateada
        return f"{nombre[:2].upper()}{apellido[:2].upper()}1234"


# ==========================================
# 👤 GESTIÓN DE USUARIOS Y SEGURIDAD
# ==========================================
@admin_bp.route("/usuarios", methods=["POST", "OPTIONS"])
def registrar_usuario():
    if request.method == "OPTIONS": return jsonify({}), 200

    data = request.get_json()
    if not all(k in data for k in ("nombre", "correo", "contraseña", "rol")): 
        return jsonify({"error": "Faltan datos obligatorios"}), 400
        
    if Usuario.query.filter_by(correo=data["correo"]).first(): 
        return jsonify({"error": "Este correo ya está registrado"}), 400

    try:
        nuevo_usuario = Usuario(
            nombre=data["nombre"], 
            correo=data["correo"], 
            contraseña=generate_password_hash(data["contraseña"]),
            rol=data["rol"], 
            puesto=data.get("puesto") if data["rol"] == 'ADMIN' else None, 
            estado="ACTIVO"
        )
        db.session.add(nuevo_usuario)
        db.session.commit()
        
        db.session.add(Bitacora(id_usuario=1, accion="REGISTRO_USUARIO", descripcion=f"Registró a {nuevo_usuario.correo}"))
        db.session.commit()
        
        return jsonify({"message": "Usuario registrado", "usuario": nuevo_usuario.correo}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# 🔑 NUEVO: CAMBIAR CONTRASEÑA
@admin_bp.route("/usuarios/<int:id_usuario>/cambiar-password", methods=["PUT", "OPTIONS"])
def cambiar_password(id_usuario):
    if request.method == "OPTIONS": return jsonify({}), 200
        
    data = request.get_json()
    nueva_password = data.get("nueva_password")

    if not nueva_password:
        return jsonify({"error": "La nueva contraseña es obligatoria"}), 400

    try:
        usuario = Usuario.query.get(id_usuario)
        if not usuario:
            return jsonify({"error": "Usuario no encontrado"}), 404

        usuario.contraseña = generate_password_hash(nueva_password)
        db.session.commit()

        # 🛡️ Bitácora de seguridad
        db.session.add(Bitacora(
            id_usuario=1, 
            accion="CAMBIO_PASSWORD", 
            descripcion=f"Se actualizó la contraseña del usuario: {usuario.correo}"
        ))
        db.session.commit()

        return jsonify({"message": "Contraseña actualizada correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ==========================================
# 🎓 GESTIÓN DE ALUMNOS (Registro con Autocreación de Usuario)
# ==========================================
@admin_bp.route('/alumnos', methods=['POST', 'OPTIONS'])
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
            return jsonify({'error': 'La fecha de nacimiento es obligatoria para generar el acceso'}), 400

        # 1. Validar que la matrícula no exista ya
        if Alumno.query.filter_by(matricula=matricula_req).first() or Usuario.query.filter_by(correo=matricula_req).first():
            return jsonify({'error': 'Esta matrícula ya está registrada en el sistema'}), 400

        # 2. Generar contraseña mágica
        password_creada = generar_password_alumno(nombre_req, apellido_req, fecha_nac_req)

        # 3. Crear Usuario (Cuenta para login)
        nuevo_usuario = Usuario(
            nombre=f"{nombre_req} {apellido_req}",
            correo=matricula_req, # El correo es la matrícula
            contraseña=generate_password_hash(password_creada),
            rol="ALUMNO",
            estado="ACTIVO"
        )
        db.session.add(nuevo_usuario)
        db.session.flush() # Guardar temporalmente para obtener id_usuario

        # 4. Crear Perfil Académico del Alumno
        nuevo_alumno = Alumno(
            matricula=matricula_req,
            nombre=nombre_req,
            apellido=apellido_req,
            fecha_nacimiento=fecha_nac_req,
            id_generacion=id_generacion_req,
            id_grupo=id_grupo_req,
            id_usuario=nuevo_usuario.id_usuario, # 🔗 Conexión Mágica
            estatus="ACTIVO",
            semestre_actual=1 
        )
        db.session.add(nuevo_alumno)
        db.session.flush() # 🔥 OBTENEMOS SU ID TEMPORAL PARA LOS PAGOS

        # 🔥 5. LA MAGIA FINANCIERA: Le clonamos todas las colegiaturas de su generación
        estructuras_generacion = EstructuraPago.query.filter_by(id_generacion=id_generacion_req).all()
        for molde in estructuras_generacion:
            nuevo_pago = Pago(
                id_alumno=nuevo_alumno.id_alumno,
                id_estructura=molde.id_estructura,
                estado='PENDIENTE',
                numero_oportunidad=1
            )
            db.session.add(nuevo_pago)
        
        # 6. Rastro en bitácora
        db.session.add(Bitacora(id_usuario=1, accion="NUEVO_ALUMNO", descripcion=f"Se inscribió al alumno {matricula_req} con todo su estado de cuenta"))
        
        db.session.commit()

        return jsonify({
            'message': 'Alumno inscrito y cuenta creada con éxito', 
            'password_generada': password_creada
        }), 201

    except Exception as e:
        db.session.rollback()
        print("🔴 Error al registrar alumno:", str(e))
        return jsonify({'error': 'Ocurrió un error al registrar el alumno'}), 500


# ==========================================
# 📊 PANEL EJECUTIVO (DASHBOARD)
# ==========================================
@admin_bp.route('/dashboard/admin', methods=['GET', 'OPTIONS'])
def obtener_datos_dashboard():
    if request.method == "OPTIONS": return jsonify({}), 200

    try:
        alumnos = Alumno.query.all()
        generaciones = Generacion.query.all()
        grupos = Grupo.query.join(Generacion).order_by(Generacion.id_generacion.desc()).limit(8).all()
        
        meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        meses_labels = []
        ingresos_data = []
        hoy = datetime.now()

        pagos_completos = db.session.query(Pago, EstructuraPago).join(
            EstructuraPago, Pago.id_estructura == EstructuraPago.id_estructura
        ).all()

        for i in range(5, -1, -1):
            mes_calc = hoy.month - i
            anio_calc = hoy.year
            if mes_calc <= 0:
                mes_calc += 12
                anio_calc -= 1
            
            meses_labels.append(meses_nombres[mes_calc - 1])
            suma_mes = 0
            for p, e in pagos_completos:
                estado_pago = str(p.estado).split('.')[-1]
                if estado_pago == 'PAGADO' and p.fecha_pago:
                    if p.fecha_pago.month == mes_calc and p.fecha_pago.year == anio_calc:
                        suma_mes += float(e.monto or 0)
            
            ingresos_data.append(suma_mes)

        grupos_pulidos = []
        for gr in grupos:
            nombre_gen = gr.generacion.nombre if gr.generacion else ""
            grupos_pulidos.append({
                "id": gr.id_grupo,
                "nombre": f"{gr.nombre_grupo} {nombre_gen}".strip()
            })

        resumen_alumnos = []
        for a in alumnos:
            tiene_adeudo = db.session.query(Pago).filter_by(
                id_alumno=a.id_alumno, estado='PENDIENTE'
            ).first() is not None
            
            resumen_alumnos.append({
                "estatus": a.estatus, 
                "tieneAdeudo": tiene_adeudo
            })

        return jsonify({
            "alumnos": resumen_alumnos, 
            "generaciones": [{"id": g.id_generacion, "nombre": g.nombre} for g in generaciones],
            "grupos": grupos_pulidos, 
            "grafica": { "labels": meses_labels, "ingresos": ingresos_data }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 🏫 GESTIÓN DE GENERACIONES Y GRUPOS 
# ==========================================
@admin_bp.route("/generaciones-grupos", methods=["GET", "POST", "OPTIONS"])
def gestionar_generaciones_grupos():
    if request.method == "OPTIONS": return jsonify({}), 200

    if request.method == "GET":
        try:
            grupos = db.session.query(Grupo, Generacion).join(
                Generacion, Grupo.id_generacion == Generacion.id_generacion
            ).order_by(Generacion.id_generacion.desc(), Grupo.nombre_grupo.asc()).all()

            resultado = []
            for gr, gen in grupos:
                activos = Alumno.query.filter_by(id_grupo=gr.id_grupo, estatus='ACTIVO').count()
                bajas = Alumno.query.filter_by(id_grupo=gr.id_grupo, estatus='BAJA').count()

                resultado.append({
                    "id_grupo": gr.id_grupo,
                    "id_generacion": gen.id_generacion,
                    "nombre_generacion": gen.nombre,
                    "nombre_grupo": gr.nombre_grupo,
                    "fecha_inicio": gen.fecha_inicio.strftime("%Y-%m-%d") if gen.fecha_inicio else None,
                    "fecha_fin": gen.fecha_fin.strftime("%Y-%m-%d") if gen.fecha_fin else None,
                    "estado": gen.estado,
                    "activos": activos,
                    "bajas": bajas
                })
            return jsonify(resultado), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    if request.method == "POST":
        data = request.get_json()
        try:
            nombre_gen = data.get('nombre_generacion')
            fecha_in = data.get('fecha_inicio')
            fecha_fn = data.get('fecha_fin')
            estado_gen = data.get('estado', 'ACTIVA')
            nombre_grupo = data.get('nombre_grupo', 'S/G').upper()
            turno_grupo = data.get('turno', 'Matutino')

            generacion = Generacion.query.filter_by(nombre=nombre_gen).first()
            
            if not generacion:
                generacion = Generacion(
                    nombre=nombre_gen,
                    fecha_inicio=fecha_in,
                    fecha_fin=fecha_fn,
                    estado=estado_gen
                )
                db.session.add(generacion)
                db.session.flush()

                # 🕰️ LA MÁQUINA DEL TIEMPO 
                try:
                    fecha_str = str(fecha_in)[:10] 
                    fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d')
                    anio_base = fecha_obj.year
                except Exception:
                    anio_base = datetime.now().year 

                meses_impares = [(8, "AGOSTO"), (9, "SEPTIEMBRE"), (10, "OCTUBRE"), (11, "NOVIEMBRE"), (12, "DICIEMBRE")]
                meses_pares = [(1, "ENERO"), (2, "FEBRERO"), (3, "MARZO"), (4, "ABRIL"), (5, "MAYO"), (6, "JUNIO"), (7, "JULIO")]

                for sem in range(1, 7):
                    anio_semestre = anio_base + (sem // 2)
                    mes_inscripcion = 1 if sem % 2 == 0 else 8
                    
                    db.session.add(EstructuraPago(
                        id_generacion=generacion.id_generacion, tipo='INSCRIPCION', semestre=sem, 
                        concepto=f'INSCRIPCIÓN {sem}° SEM', monto=200,
                        mes=mes_inscripcion, anio=anio_semestre 
                    ))
                    
                    meses_a_usar = meses_pares if sem % 2 == 0 else meses_impares
                    
                    for numero_mes, nombre_mes in meses_a_usar:
                        db.session.add(EstructuraPago(
                            id_generacion=generacion.id_generacion, tipo='MENSUALIDAD', semestre=sem,
                            concepto=f'{nombre_mes} - {sem}° SEM', monto=450, mes=numero_mes, anio=anio_semestre 
                        ))

            existe_grupo = Grupo.query.filter_by(nombre_grupo=nombre_grupo, id_generacion=generacion.id_generacion).first()
            if existe_grupo:
                return jsonify({"error": f"El Grupo '{nombre_grupo}' ya existe en esta generación."}), 400

            nuevo_grupo = Grupo(
                nombre_grupo=nombre_grupo,
                turno=turno_grupo,
                id_generacion=generacion.id_generacion
            )
            db.session.add(nuevo_grupo)
            db.session.commit()

            return jsonify({"message": "Grupo y Generación registrados correctamente"}), 201
            
        except Exception as e:
            db.session.rollback()
            print("🔴 ERROR FATAL EN CREAR GENERACIÓN:")
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

@admin_bp.route("/generaciones-grupos/<int:id_grupo>", methods=["PUT", "OPTIONS"])
def actualizar_generacion_grupo(id_grupo):
    if request.method == "OPTIONS": return jsonify({}), 200
    data = request.get_json()
    try:
        grupo = Grupo.query.get(id_grupo)
        if not grupo: return jsonify({"error": "Grupo no encontrado"}), 404

        if 'nombre_grupo' in data:
            grupo.nombre_grupo = data['nombre_grupo'].upper()

        generacion = Generacion.query.get(grupo.id_generacion)
        if generacion:
            if 'nombre_generacion' in data: generacion.nombre = data['nombre_generacion']
            if 'fecha_inicio' in data: generacion.fecha_inicio = data['fecha_inicio']
            if 'fecha_fin' in data: generacion.fecha_fin = data['fecha_fin']
            if 'estado' in data: generacion.estado = data['estado']

        db.session.commit()
        return jsonify({"message": "Actualizado correctamente"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500