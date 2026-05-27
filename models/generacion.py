from extensions import db
class Generacion(db.Model):
    __tablename__ = 'generacion'

    id_generacion = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    estado = db.Column(db.Enum('ACTIVA', 'CERRADA'), default='ACTIVA')

    # Modificaciones aplicadas aquí abajo:
    alumnos = db.relationship('Alumno', back_populates='generacion', cascade='all, delete', passive_deletes=True)
    estructuras = db.relationship('EstructuraPago', back_populates='generacion', cascade='all, delete', passive_deletes=True)
    grupos = db.relationship('Grupo', back_populates='generacion', cascade='all, delete', passive_deletes=True)


""" 
class Generacion(db.Model):
    __tablename__ = 'generacion'

    id_generacion = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    estado = db.Column(db.Enum('ACTIVA', 'CERRADA'), default='ACTIVA')

    alumnos = db.relationship('Alumno', back_populates='generacion')
    estructuras = db.relationship('EstructuraPago', back_populates='generacion')
    grupos = db.relationship('Grupo', back_populates='generacion') """