from .usuario import Usuario
from .generacion import Generacion
from .grupo import Grupo
from .alumno import Alumno
from .estructura_pago import EstructuraPago
from .pago import Pago
from .bitacora import Bitacora

# Esto permite que hagas: from models import Usuario, Alumno...
__all__ = [
    "Usuario", 
    "Generacion", 
    "Grupo", 
    "Alumno", 
    "EstructuraPago", 
    "Pago", 
    "Bitacora"
]