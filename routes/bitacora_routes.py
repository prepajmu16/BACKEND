from flask import Blueprint, jsonify, request
from extensions import db
from models.bitacora import Bitacora
# 🛡️ IMPORTAMOS EL ESCUDO DE SEGURIDAD
from flask_jwt_extended import verify_jwt_in_request, get_jwt

bitacora_bp = Blueprint('bitacora_bp', __name__)

def determinar_modulo(accion):
    """
    Función inteligente que lee la acción y deduce a qué módulo pertenece
    para no tener que modificar la base de datos, usando los nombres REALES del menú.
    """
    accion = str(accion).upper()
    
    # Módulo Configuración -> Personal
    if any(k in accion for k in ['USUARIO', 'PERSONAL', 'PERFIL']):
        return 'PERSONAL'
        
    # Módulo Académico -> Alumnos
    if any(k in accion for k in ['ALUMNO', 'MATRICULA', 'PROMOCION']):
        return 'ALUMNOS'
        
    # Módulo Financiero -> Pagos
    if any(k in accion for k in ['COBRO', 'PAGO', 'RECIBO', 'CONCEPTO', 'CARGO']):
        return 'PAGOS'
        
    # Módulo Académico -> Generaciones
    if 'GENERACION' in accion:
        return 'GENERACIONES'
        
    # Módulo Académico -> Grupos
    if 'GRUPO' in accion:
        return 'GRUPOS'
        
    # Módulo Financiero -> Reportes
    if any(k in accion for k in ['DESCARGA', 'REPORTE', 'CORTE']):
        return 'REPORTES'
        
    # Acciones de acceso (Login, cambiar contraseñas) o cosas generales
    if any(k in accion for k in ['LOGIN', 'PASSWORD']):
        return 'SISTEMA'
        
    return 'SISTEMA' # Valor por defecto

# ✅ 'OPTIONS' para que Angular no bloquee la petición por CORS
@bitacora_bp.route('/bitacora', methods=['GET', 'OPTIONS'])
def obtener_bitacora():
    
    # ✅ Respondemos a la petición de seguridad de Angular
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    # 🛡️ VALIDACIÓN DE TOKEN Y SEGURIDAD MÁXIMA
    try: verify_jwt_in_request()
    except Exception: return jsonify({"error": "Sesión inválida o token ausente"}), 401
    
    operador = get_jwt()
    # ⛔ BLOQUEO ESTRICTO: Solo el personal de Sistemas puede auditar el sistema
    if operador.get('rol') != 'SISTEMAS':
        return jsonify({"error": "Acceso denegado. Solo el nivel SISTEMAS puede visualizar la bitácora."}), 403

    try:
        # Obtenemos los últimos 100 registros
        logs = Bitacora.query.order_by(Bitacora.fecha.desc()).limit(100).all()
        
        resultado = []
        for log in logs:
            # Protegemos el código en caso de que alguna acción venga vacía
            accion_texto = log.accion if log.accion else "SISTEMA"
            
            # 🧠 Usamos la inteligencia para adivinar el módulo con los nombres de tu menú
            modulo_real = determinar_modulo(accion_texto)
            
            # 🌐 Leemos la IP directamente de la base de datos
            ip_real = getattr(log, 'ip', '127.0.0.1')
            
            resultado.append({
                "id": log.id_bitacora,
                "fecha": log.fecha.strftime("%Y-%m-%dT%H:%M:%S") if log.fecha else None,
                "usuario": log.usuario.nombre if log.usuario else "Desconocido",
                "accion": accion_texto,
                "modulo": modulo_real, 
                "detalle": log.descripcion, 
                "ip": ip_real 
            })
            
        return jsonify(resultado), 200

    except Exception as e:
        print(f"Error al obtener bitácora: {e}")
        return jsonify({"mensaje": "Error interno"}), 500
    
""" from flask import Blueprint, jsonify, request
from extensions import db
from models.bitacora import Bitacora

bitacora_bp = Blueprint('bitacora_bp', __name__)

def determinar_modulo(accion):
    
    accion = str(accion).upper()
    
    # Módulo Configuración -> Personal
    if any(k in accion for k in ['USUARIO', 'PERSONAL', 'PERFIL']):
        return 'PERSONAL'
        
    # Módulo Académico -> Alumnos
    if any(k in accion for k in ['ALUMNO', 'MATRICULA', 'PROMOCION']):
        return 'ALUMNOS'
        
    # Módulo Financiero -> Pagos
    if any(k in accion for k in ['COBRO', 'PAGO', 'RECIBO', 'CONCEPTO', 'CARGO']):
        return 'PAGOS'
        
    # Módulo Académico -> Generaciones
    if 'GENERACION' in accion:
        return 'GENERACIONES'
        
    # Módulo Académico -> Grupos
    if 'GRUPO' in accion:
        return 'GRUPOS'
        
    # Módulo Financiero -> Reportes
    if any(k in accion for k in ['DESCARGA', 'REPORTE', 'CORTE']):
        return 'REPORTES'
        
    # Acciones de acceso (Login, cambiar contraseñas) o cosas generales
    if any(k in accion for k in ['LOGIN', 'PASSWORD']):
        return 'SISTEMA'
        
    return 'SISTEMA' # Valor por defecto

# ✅ 'OPTIONS' para que Angular no bloquee la petición por CORS
@bitacora_bp.route('/bitacora', methods=['GET', 'OPTIONS'])
def obtener_bitacora():
    
    # ✅ Respondemos a la petición de seguridad de Angular
    if request.method == 'OPTIONS':
        return jsonify({}), 200

    try:
        # Obtenemos los últimos 100 registros
        logs = Bitacora.query.order_by(Bitacora.fecha.desc()).limit(100).all()
        
        resultado = []
        for log in logs:
            # Protegemos el código en caso de que alguna acción venga vacía
            accion_texto = log.accion if log.accion else "SISTEMA"
            
            # 🧠 Usamos la inteligencia para adivinar el módulo con los nombres de tu menú
            modulo_real = determinar_modulo(accion_texto)
            
            # 🌐 Leemos la IP directamente de la base de datos
            ip_real = getattr(log, 'ip', '127.0.0.1')
            
            resultado.append({
                "id": log.id_bitacora,
                "fecha": log.fecha.strftime("%Y-%m-%dT%H:%M:%S") if log.fecha else None,
                "usuario": log.usuario.nombre if log.usuario else "Desconocido",
                "accion": accion_texto,
                "modulo": modulo_real, 
                "detalle": log.descripcion, 
                "ip": ip_real 
            })
            
        return jsonify(resultado), 200

    except Exception as e:
        print(f"Error al obtener bitácora: {e}")
        return jsonify({"mensaje": "Error interno"}), 500 """