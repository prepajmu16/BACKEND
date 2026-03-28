from extensions import db

class Pago(db.Model):
    __tablename__ = 'pagos'

    id_pago = db.Column(db.Integer, primary_key=True)
    id_alumno = db.Column(db.Integer, db.ForeignKey('alumno.id_alumno'), nullable=False)
    id_estructura = db.Column(db.Integer, db.ForeignKey('estructura_pago.id_estructura'), nullable=False)

    fecha_pago = db.Column(db.Date)
    
    # 🚩 CAMBIO 1: Columna para registrar el dinero que va dejando el alumno (Abonos)
    monto_abonado = db.Column(db.Numeric(10, 2), default=0.00)
    
    # 🚩 CAMBIO 2: Se agregó 'PARCIAL' (y 'CANCELADO' por seguridad) al ENUM
    estado = db.Column(db.Enum('PENDIENTE', 'PARCIAL', 'PAGADO', 'CANCELADO'), default='PENDIENTE')
    
    folio = db.Column(db.String(50))
    numero_oportunidad = db.Column(db.Integer)

    alumno = db.relationship('Alumno', back_populates='pagos')
    estructura = db.relationship('EstructuraPago', back_populates='pagos')