from extensions import db

class EstructuraPago(db.Model):
    __tablename__ = 'estructura_pago'

    id_estructura = db.Column(db.Integer, primary_key=True)
    id_generacion = db.Column(db.Integer, db.ForeignKey('generacion.id_generacion'), nullable=False)
    tipo = db.Column(db.Enum('INSCRIPCION', 'MENSUALIDAD', 'EEE'), nullable=False)
    semestre = db.Column(db.Integer, default=1) 
    concepto = db.Column(db.String(100))
    mes = db.Column(db.Integer)
    anio = db.Column(db.Integer)  
    monto = db.Column(db.Numeric(10, 2), nullable=False)

    generacion = db.relationship('Generacion', back_populates='estructuras')
    pagos = db.relationship('Pago', back_populates='estructura')