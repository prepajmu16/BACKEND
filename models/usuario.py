from extensions import db

class Usuario(db.Model):
    __tablename__ = 'usuario'

    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(100), unique=True, nullable=False)
    contraseña = db.Column(db.String(255), nullable=False)
    # 🔥 CAMBIO: Usamos String en lugar de Enum para dar total libertad a los roles
    rol = db.Column(db.String(20), nullable=False) 
    puesto = db.Column(db.String(50), nullable=True)
    # 🔥 CAMBIO: También aquí para evitar líos con nuevos estados
    estado = db.Column(db.String(20), default='ACTIVO')

    alumno = db.relationship('Alumno', back_populates='usuario', uselist=False)
    bitacoras = db.relationship('Bitacora', back_populates='usuario')
    
    def to_dict(self):
        return {
            "id": self.id_usuario,
            "nombre": self.nombre,
            "usuario": self.correo,
            "rol": self.rol,
            "puesto": self.puesto,
            "estado": self.estado
        }