# --- Importamos el conector Flask para MySQL ---
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib

# --- Inicializamos la aplicación Flask ---
app = Flask(__name__)

# --- Configuramos la clave secreta de la app ---
# Se usa para encriptar la información de la sesión (por ejemplo, los datos del usuario logueado)
# En un proyecto real, esta clave debería ser más segura
app.secret_key = "clave_segura_flask123"

# --- Configuración de la conexión a la base de datos MySQL ---
app.config['MYSQL_HOST'] = 'localhost'         # Servidor de la BD
app.config['MYSQL_USER'] = 'root'              # Usuario de la BD
app.config['MYSQL_PASSWORD'] = 'root'          # Contraseña de la BD
app.config['MYSQL_DB'] = 'ObligatorioBD1'      # Nombre de la base de datos

# --- Inicializamos el objeto MySQL ---
mysql = MySQL(app)



# =====================================================
#                 RUTA DE LOGIN
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    # Si se envió el formulario (método POST)
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]

        # Encriptamos la contraseña con MD5 para compararla con la guardada
        contraseña_hasheada = hashlib.md5(contraseña.encode()).hexdigest()

        # Creamos un cursor para ejecutar la consulta
        cursor = mysql.connection.cursor()

        # Consultamos si existe el usuario con ese correo
        query = "SELECT correo, contraseña, es_administrador FROM login WHERE correo = %s"
        cursor.execute(query, (correo,))
        usuario = cursor.fetchone()  # Devuelve una tupla: (correo, contraseña, es_administrador)

        cursor.close()

        # Si no existe el correo
        if not usuario:
            return render_template("login.html", error="El correo no está registrado.")
        else:
            # Comparamos la contraseña ingresada (hasheada) con la almacenada en la BD
            if usuario[1] == contraseña_hasheada:
                # Guardamos datos del usuario en la sesión
                session["usuario"] = {
                    "correo": usuario[0],
                    "es_admin": usuario[2] == 1
                }
                return redirect(url_for("inicio"))
            else:
                return render_template("login.html", error="Contraseña incorrecta.")

    # Si se accede por método GET, solo muestra el formulario
    return render_template("login.html")


# =====================================================
#                RUTA DE INICIO
# =====================================================
@app.route("/inicio")
def inicio():
    # Verificamos si el usuario está logueado
    if "usuario" not in session:
        return redirect(url_for("login"))

    # Mostramos una página de bienvenida simple
    usuario = session["usuario"]
    return f"Bienvenido, {usuario['correo']} (Admin: {usuario['es_admin']})"


# =====================================================
#          RUTA PARA RECUPERAR CONTRASEÑA
# =====================================================
@app.route('/recuperar_contraseña')
def recuperar_contraseña():
    return "Página de recuperación de contraseña (en construcción)"


# =====================================================
#                RUTA PRINCIPAL
# =====================================================
@app.route("/")
def index():
    return redirect(url_for("login"))


# =====================================================
#          EJECUTAR EL SERVIDOR FLASK
# =====================================================
if __name__ == '__main__':
    app.run(debug=True)
