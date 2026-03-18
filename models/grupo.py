from extensions import db

class Grupo(db.Model):
    __tablename__ = 'grupos'

    id_grupo = db.Column(db.Integer, primary_key=True)
    nombre_grupo = db.Column(db.String(10), nullable=False)
    turno = db.Column(db.Enum('Matutino', 'Vespertino'), default='Matutino')
    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)

    __table_args__ = (db.UniqueConstraint('nombre_grupo', 'id_generacion', name='_grupo_gen_uc'),)

    generacion = db.relationship('Generacion', back_populates='grupos')
    alumnos = db.relationship('Alumno', back_populates='grupo')