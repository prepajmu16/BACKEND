from extensions import db
from datetime import datetime, timezone

class Bitacora(db.Model):
    __tablename__ = 'bitacora'
    id_bitacora = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id_usuario'), nullable=False)

    accion = db.Column(db.String(100))
    descripcion = db.Column(db.Text)
    # ✅ NUEVA COLUMNA
    ip = db.Column(db.String(45)) 
    
    fecha = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    usuario = db.relationship('Usuario', back_populates='bitacoras')