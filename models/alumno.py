from extensions import db

class Alumno(db.Model):
    __tablename__ = 'alumno'

    id_alumno = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    
    # 🔥 AQUÍ ESTÁ EL CAMPO QUE FALTABA 🔥
    fecha_nacimiento = db.Column(db.Date, nullable=True)

    estatus = db.Column(db.Enum('ACTIVO', 'BAJA', 'SUSPENDIDO', 'EGRESADO'), default='ACTIVO')
    semestre_actual = db.Column(db.Integer, default=1, nullable=False)

    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), unique=True)
    id_grupo = db.Column(db.Integer, db.ForeignKey('grupos.id_grupo'))

    generacion = db.relationship('Generacion', back_populates='alumnos')
    usuario = db.relationship('Usuario', back_populates='alumno')
    grupo = db.relationship('Grupo', back_populates='alumnos')
    pagos = db.relationship('Pago', back_populates='alumno')

    def to_dict(self):
        return {
            "id_alumno": self.id_alumno,
            "matricula": self.matricula,
            "nombre": self.nombre,
            "apellido": self.apellido,
            # 🔥 AQUÍ TAMBIÉN LO AGREGAMOS PARA QUE VIAJE A ANGULAR 🔥
            "fecha_nacimiento": self.fecha_nacimiento.strftime('%Y-%m-%d') if self.fecha_nacimiento else None,
            "estatus": self.estatus,
            "semestre_actual": self.semestre_actual,
            "id_generacion": self.id_generacion,
            "id_grupo": self.id_grupo,
            "nombre_gen": self.generacion.nombre if self.generacion else "Sin Generación",
            "letra_grupo": self.grupo.nombre_grupo if self.grupo else "S/G",
            "tieneAdeudo": any(p.estado == 'PENDIENTE' for p in self.pagos)
        }