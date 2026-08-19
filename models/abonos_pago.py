from datetime import datetime
from extensions import db # O la importación que uses para tu instancia de SQLAlchemy

class AbonoPago(db.Model):
    __tablename__ = 'abonos_pago'

    id_abono = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_pago = db.Column(db.Integer, db.ForeignKey('pagos.id_pago', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    monto_abono = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_abono = db.Column(db.Date, nullable=False)
    folio = db.Column(db.String(50), nullable=False)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)

    # Relación inversa (opcional pero muy útil) para acceder a los abonos desde un objeto Pago
    # Si en tu modelo Pago quieres usar algo como: pago.abonos
    pago = db.relationship('Pago', backref=db.backref('abonos', lazy=True, cascade="all, delete"))

    def __repr__(self):
        return f"<AbonoPago {self.id_abono} - Folio: {self.folio}>"