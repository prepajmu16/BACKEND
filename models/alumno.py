from extensions import db
from datetime import datetime # 👈 IMPORTANTE: No olvides esta línea arriba en tu archivo

class Alumno(db.Model):
    __tablename__ = 'alumno'

    id_alumno = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    
    # 🚩 CAMBIO: Nueva columna para la fecha de baja
    fecha_baja = db.Column(db.Date, nullable=True)

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
        ahora = datetime.now()
        tiene_adeudo_real = False
        
        # 🔥 LÓGICA INTELIGENTE (Y OPTIMIZADA) 🔥
        for p in self.pagos:
            # ✅ También consideramos 'PARCIAL' como deuda, no solo 'PENDIENTE'
            if p.estado in ['PENDIENTE', 'PARCIAL']: 
                # ✅ Usamos la relación directa (p.estructura) en lugar de hacer otra consulta a la DB
                estructura = p.estructura 

                if estructura:
                    if estructura.tipo == 'INSCRIPCION':
                        tiene_adeudo_real = True
                        break
                    elif estructura.tipo == 'MENSUALIDAD':
                        if estructura.anio < ahora.year:
                            tiene_adeudo_real = True
                            break
                        elif estructura.anio == ahora.year and estructura.mes <= ahora.month:
                            tiene_adeudo_real = True
                            break
                else:
                    tiene_adeudo_real = True
                    break

        return {
            "id_alumno": self.id_alumno,
            "matricula": self.matricula,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "fecha_nacimiento": self.fecha_nacimiento.strftime('%Y-%m-%d') if self.fecha_nacimiento else None,
            "fecha_baja": self.fecha_baja.strftime('%Y-%m-%d') if self.fecha_baja else None,
            "estatus": self.estatus,
            "semestre_actual": self.semestre_actual,
            "id_generacion": self.id_generacion,
            "id_grupo": self.id_grupo,
            "nombre_gen": self.generacion.nombre if self.generacion else "Sin Generación",
            "letra_grupo": self.grupo.nombre_grupo if self.grupo else "S/G",
            "tieneAdeudo": tiene_adeudo_real 
        }

""" from extensions import db
from datetime import datetime # 👈 IMPORTANTE: No olvides esta línea arriba en tu archivo

class Alumno(db.Model):
    __tablename__ = 'alumno'

    id_alumno = db.Column(db.Integer, primary_key=True)
    matricula = db.Column(db.String(20), unique=True, nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    apellido = db.Column(db.String(100), nullable=False)
    
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    
    # 🚩 CAMBIO: Nueva columna para la fecha de baja
    fecha_baja = db.Column(db.Date, nullable=True)

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
        ahora = datetime.now()
        tiene_adeudo_real = False
        
        # 🔥 LÓGICA INTELIGENTE: Diferenciar deudas reales de cobros futuros 🔥
        for p in self.pagos:
            if p.estado == 'PENDIENTE':
                # Buscamos de qué trata este cobro (asumiendo que EstructuraPago está en este mismo archivo)
                estructura = EstructuraPago.query.get(p.id_estructura)

                if estructura:
                    # Las inscripciones pendientes siempre son deuda
                    if estructura.tipo == 'INSCRIPCION':
                        tiene_adeudo_real = True
                        break
                    # Las mensualidades solo son deuda si el mes ya llegó o ya pasó
                    elif estructura.tipo == 'MENSUALIDAD':
                        if estructura.anio < ahora.year:
                            tiene_adeudo_real = True
                            break
                        elif estructura.anio == ahora.year and estructura.mes <= ahora.month:
                            tiene_adeudo_real = True
                            break
                else:
                    # Si es un cargo extra suelto sin estructura de fecha, lo contamos como deuda
                    tiene_adeudo_real = True
                    break

        return {
            "id_alumno": self.id_alumno,
            "matricula": self.matricula,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "fecha_nacimiento": self.fecha_nacimiento.strftime('%Y-%m-%d') if self.fecha_nacimiento else None,
            "fecha_baja": self.fecha_baja.strftime('%Y-%m-%d') if self.fecha_baja else None,
            "estatus": self.estatus,
            "semestre_actual": self.semestre_actual,
            "id_generacion": self.id_generacion,
            "id_grupo": self.id_grupo,
            "nombre_gen": self.generacion.nombre if self.generacion else "Sin Generación",
            "letra_grupo": self.grupo.nombre_grupo if self.grupo else "S/G",
            "tieneAdeudo": tiene_adeudo_real # 🚩 Enviamos el cálculo limpio a Angular
        } """