from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()

# ==============================
# USUARIO
# ==============================
class Usuario(db.Model):
    __tablename__ = 'usuario'

    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.Enum('ADMIN','ALUMNO'), nullable=False)
    
    # ✅ NUEVO CAMPO: Puesto (Cargo administrativo)
    # Es nullable=True porque los alumnos no tienen puesto
    puesto = db.Column(db.String(50), nullable=True)

    estado = db.Column(db.Enum('ACTIVO','INACTIVO'), default='ACTIVO')

    # Relaciones
    alumno = db.relationship('Alumno', back_populates='usuario', uselist=False)
    bitacoras = db.relationship('Bitacora', back_populates='usuario')
    
    def to_dict(self):
        return {
            "id": self.id_usuario,
            "nombre": self.nombre,
            "usuario": self.correo, # Recuerda: puede ser correo o matrícula
            "rol": self.rol,
            "puesto": self.puesto,  # Si es alumno, esto devolverá null automáticamente
            "estado": self.estado
        }


# ==============================
# GENERACION
# ==============================
class Generacion(db.Model):
    __tablename__ = 'generacion'

    id_generacion = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    estado = db.Column(db.Enum('ACTIVA','CERRADA'), default='ACTIVA')

    alumnos = db.relationship('Alumno', back_populates='generacion')
    estructuras = db.relationship('EstructuraPago', back_populates='generacion')
    grupos = db.relationship('Grupo', back_populates='generacion')


# ==============================
# GRUPO
# ==============================
class Grupo(db.Model):
    __tablename__ = 'grupos'

    id_grupo = db.Column(db.Integer, primary_key=True)
    nombre_grupo = db.Column(db.String(10), nullable=False)
    turno = db.Column(db.Enum('Matutino','Vespertino'), default='Matutino')
    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)

    generacion = db.relationship('Generacion', back_populates='grupos')
    alumnos = db.relationship('Alumno', back_populates='grupo')


# ==============================
# ALUMNO
# ==============================
class Alumno(db.Model):
    __tablename__ = 'alumno'

    id_alumno = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    estatus = db.Column(db.Enum('ACTIVO','BAJA','SUSPENDIDO'), default='ACTIVO')

    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), unique=True)
    id_grupo = db.Column(db.Integer, db.ForeignKey('grupos.id_grupo'))

    generacion = db.relationship('Generacion', back_populates='alumnos')
    usuario = db.relationship('Usuario', back_populates='alumno')
    grupo = db.relationship('Grupo', back_populates='alumnos')
    pagos = db.relationship('Pago', back_populates='alumno')


# ==============================
# ESTRUCTURA DE PAGO
# ==============================
# ==============================
# ESTRUCTURA DE PAGO
# ==============================
class EstructuraPago(db.Model):
    __tablename__ = 'estructura_pago'

    id_estructura = db.Column(db.Integer, primary_key=True)
    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)
    tipo = db.Column(db.Enum('INSCRIPCION','MENSUALIDAD','EEE'), nullable=False)
    concepto = db.Column(db.String(100))
    mes = db.Column(db.Integer)
    
    # ✅ CORRECCIÓN: Quitamos el mapeo 'año' y dejamos el nombre real de tu tabla
    anio = db.Column(db.Integer)  
    
    monto = db.Column(db.Numeric(10,2), nullable=False)

    generacion = db.relationship('Generacion', back_populates='estructuras')
    pagos = db.relationship('Pago', back_populates='estructura')


# ==============================
# PAGO
# ==============================
class Pago(db.Model):
    __tablename__ = 'pagos'

    id_pago = db.Column(db.Integer, primary_key=True)
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumno.id_alumno'), nullable=False)
    id_estructura = db.Column(db.Integer, db.ForeignKey('estructura_pago.id_estructura'), nullable=False)

    fecha_pago = db.Column(db.Date)
    monto_pagado = db.Column(db.Numeric(10,2))
    estado = db.Column(db.Enum('PENDIENTE','PAGADO'), default='PENDIENTE')
    folio = db.Column(db.String(50))
    numero_oportunidad = db.Column(db.Integer)

    alumno = db.relationship('Alumno', back_populates='pagos')
    estructura = db.relationship('EstructuraPago', back_populates='pagos')


# ==============================
# BITACORA
# ==============================
class Bitacora(db.Model):
    __tablename__ = 'bitacora'
    id_bitacora = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), nullable=False)

    accion = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    fecha = db.Column(
    db.DateTime,
    default=lambda: datetime.now(timezone.utc),
    onupdate=lambda: datetime.now(timezone.utc)

    )
    usuario = db.relationship('Usuario', back_populates='bitacoras')