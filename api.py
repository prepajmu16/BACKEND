from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta
 
# Importamos la base de datos y la configuración
from extensions import db
from config import config
 
# Importamos los Blueprints
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.alumno_routes import alumno_bp
from routes.catalogo_routes import catalogo_bp
from routes.caja_routes import caja_bp
from routes.reportes_routes import reportes_bp
from routes.bitacora_routes import bitacora_bp
 
app = Flask(__name__)
 
# ==========================
# 🔐 CONFIGURACIÓN DE SEGURIDAD
# ==========================
app.config["JWT_SECRET_KEY"] = "super-clave-secreta-residencia-2025"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2)
jwt = JWTManager(app)
 
# ==========================
# CONFIGURACIÓN APP Y BD
# ==========================
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "http://localhost:4200",
            "http://192.168.1.108:4200",
            "http://192.168.1.108",
            "http://192.168.100.11:4200",
            "http://192.168.100.11"],
                
        "allow_headers": ["Authorization", "Content-Type"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})
app.config.from_object(config['development'])
db.init_app(app)
 
# ==========================
# 🛡️ CREACIÓN AUTOMÁTICA DEL ADMIN
# Se ejecuta al levantar Flask, solo si no existe el usuario.
# ==========================
def crear_admin_inicial():
    from models import Usuario
    from werkzeug.security import generate_password_hash
 
    existe = Usuario.query.filter_by(correo='admin3@gmail.com').first()
    if not existe:
        admin = Usuario(
            nombre='Administrador',
            correo='admin3@gmail.com',
            contraseña=generate_password_hash('Admin2026'),
            rol='SISTEMAS',
            puesto='Soporte Tecnico',
            estado='ACTIVO'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Usuario SISTEMAS creado: admin3@gmail.com / Admin2026")
    else:
        print(" ℹ️  Usuario admin ya existe, no se creó uno nuevo.")
 
# ==========================
# REGISTRO DE RUTAS (BLUEPRINTS)
# ==========================
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api')
app.register_blueprint(alumno_bp, url_prefix='/api')
app.register_blueprint(catalogo_bp, url_prefix='/api')
app.register_blueprint(caja_bp, url_prefix='/api')
app.register_blueprint(reportes_bp, url_prefix='/api')
app.register_blueprint(bitacora_bp, url_prefix='/api')
 
@app.route("/")
def home():
    return jsonify({"message": "API Sistema Prepa activa y modularizada 🚀"})
 
# ==========================
# INICIO DE LA APP
# ==========================
with app.app_context():
    db.create_all()
    crear_admin_inicial()  # 👈 Se ejecuta aquí, una vez al arrancar
 
if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000, debug=True) 

""" from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from datetime import timedelta

# Importamos la base de datos y la configuración
from extensions import db
from config import config

# Importamos los Blueprints (Los cajones que acabamos de crear)
from routes.auth_routes import auth_bp
from routes.admin_routes import admin_bp
from routes.alumno_routes import alumno_bp
from routes.catalogo_routes import catalogo_bp
from routes.caja_routes import caja_bp
from routes.reportes_routes import reportes_bp
from routes.bitacora_routes import bitacora_bp

app = Flask(__name__)

# ==========================
# 🔐 CONFIGURACIÓN DE SEGURIDAD
# ==========================
app.config["JWT_SECRET_KEY"] = "super-clave-secreta-residencia-2025" 
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=2) 
jwt = JWTManager(app)

# ==========================
# CONFIGURACIÓN APP Y BD
# ==========================
# Configuración Maestra de CORS
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:4200"],
        "allow_headers": ["Authorization", "Content-Type"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    }
})
app.config.from_object(config['development'])
db.init_app(app)
# ==========================
# REGISTRO DE RUTAS (BLUEPRINTS)
# ==========================
app.register_blueprint(auth_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api',)
app.register_blueprint(alumno_bp, url_prefix='/api')
app.register_blueprint(catalogo_bp, url_prefix='/api')
app.register_blueprint(caja_bp, url_prefix='/api')
app.register_blueprint(reportes_bp, url_prefix='/api')
app.register_blueprint(bitacora_bp, url_prefix='/api') # Registro del Blueprint de bitácora

@app.route("/")
def home():
    return jsonify({"message": "API Sistema Prepa activa y modularizada 🚀"})

# ==========================
# INICIO DE LA APP
# ==========================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)  """