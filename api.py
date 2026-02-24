from flask import Flask, jsonify, request
from modelos import db, Generacion,Usuario
from config import config
from flask_cors import CORS
from werkzeug.security import generate_password_hash

app = Flask(__name__)
CORS(app, origins=["http://localhost:4200"])

app.config.from_object(config['development'])
db.init_app(app)

@app.route("/")
def home():
    return jsonify({"message": "API Sistema Prepa activa 🚀"})

@app.route("/generaciones", methods=[ "POST"])
def registrar_generacion():
    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    nueva_gen = Generacion(
        nombre=data["nombre"],
        fecha_inicio=data["fecha_inicio"],
        fecha_fin=data["fecha_fin"]
    )

    db.session.add(nueva_gen)
    db.session.commit()

    return jsonify({"message": "Generación creada correctamente"}), 201

@app.route("/generaciones", methods=["GET"])
def listar_generaciones():

    generaciones = Generacion.query.all()

    resultado = []

    for g in generaciones:
        resultado.append({
            "id": g.id_generacion,
            "nombre": g.nombre,
            "fecha_inicio": g.fecha_inicio.strftime("%Y-%m-%d"),
            "fecha_fin": g.fecha_fin.strftime("%Y-%m-%d"),
            "estado": g.estado
        })

    return jsonify(resultado), 200

@app.route("/usuarios", methods=["POST"])
def registrar_usuario():

    data = request.get_json()

    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    # Validar campos obligatorios
    if not all(k in data for k in ("nombre", "correo", "contraseña", "rol")):
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    # Verificar si ya existe el correo
    usuario_existente = Usuario.query.filter_by(correo=data["correo"]).first()
    if usuario_existente:
        return jsonify({"error": "El correo ya está registrado"}), 400

    # Encriptar contraseña
    password_hash = generate_password_hash(data["contraseña"])

    nuevo_usuario = Usuario(
        nombre=data["nombre"],
        correo=data["correo"],
        contraseña=password_hash,
        rol=data["rol"],  # ADMIN o ALUMNO
        estado="ACTIVO"
    )

    db.session.add(nuevo_usuario)
    db.session.commit()

    """ nueva_accion = Bitacora(
    id_usuario=1, # Por ahora puedes usar el ID del admin logueado
    accion="REGISTRO_USUARIO",
    descripcion=f"Se registró al usuario {nuevo_usuario.correo} con rol {nuevo_usuario.rol}"
    )
    db.session.add(nueva_accion)
    db.session.commit() """

    return jsonify({"message": "Usuario registrado correctamente"}), 201

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)