from extensions import db
from datetime import datetime

class Bitacora(db.Model):
    __tablename__ = 'bitacora'
    id_bitacora = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), nullable=False)

    accion = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    ip = db.Column(db.String(45)) 
    
    # 🕒 Quitamos el "timezone.utc" para evitar la hora de Londres
    fecha = db.Column(
        db.DateTime,
        default=datetime.now
    )
    
    usuario = db.relationship('Usuario', back_populates='bitacoras')