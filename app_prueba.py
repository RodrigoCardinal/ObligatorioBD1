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



# --------RUTA DE LOGIN--------
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Muestra el formulario de inicio de sesión (GET)
    o procesa el inicio de sesión del usuario (POST).
    Verifica el correo y la contraseña hasheada (MD5).
    Si es correcto, guarda los datos en la sesión y redirige a /inicio.
    """
    if request.method == "POST":
        # Obtener los datos del formulario
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]

        # Encriptar la contraseña ingresada con MD5
        contraseña_hasheada = hashlib.md5(contraseña.encode()).hexdigest()

        # Crear cursor para consultar la BD
        cursor = mysql.connection.cursor()

        # Buscar usuario por correo
        query = "SELECT correo, contraseña, es_administrador FROM login WHERE correo = %s"
        cursor.execute(query, (correo,))
        usuario = cursor.fetchone()
        cursor.close()

        # Si el usuario no existe
        if not usuario:
            return render_template("login.html", error="El correo no está registrado.")

        # Si existe, comparar contraseñas
        if usuario[1] == contraseña_hasheada:
            # Guardar datos del usuario en sesión
            session["usuario"] = {
                "correo": usuario[0],
                "es_admin": usuario[2] == 1
            }
            return redirect(url_for("inicio"))
        else:
            return render_template("login.html", error="Contraseña incorrecta.")

    # Si es GET → mostrar el formulario
    return render_template("login.html")


# --------RUTA DE INICIO--------
@app.route("/inicio")
def inicio():
    """
    Página principal del sistema (solo accesible si hay sesión activa).
    Muestra una pantalla de bienvenida con los datos del usuario.
    """
    if "usuario" not in session:
        # Si no hay sesión, redirige al login
        return redirect(url_for("login"))
    # Renderiza la página principal pasando los datos del usuario
    return render_template("inicio.html", usuario=session["usuario"])


# --------RUTA PARA RECUPERAR CONTRASEÑA--------
@app.route("/recuperar_contraseña", methods=["GET", "POST"])
def recuperar_contraseña():
    """
    Muestra el formulario de recuperación de contraseña.
    Verifica si el correo existe en la base de datos.
    Si existe, guarda temporalmente el correo en la sesión
    y redirige al formulario para cambiar la contraseña.
    """
    if request.method == "POST":
        correo = request.form["correo"].strip()

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT correo FROM login WHERE correo = %s", (correo,))
        resultado = cursor.fetchone()
        cursor.close()

        if resultado:
            # Guardamos el correo en sesión para usarlo en el siguiente paso
            session["correo_para_recuperar"] = correo
            return redirect(url_for("cambiar_contraseña"))
        else:
            return render_template("recuperar_contraseña.html", error="El correo no está registrado.")

    # Si es GET → mostrar formulario vacío
    return render_template("recuperar_contraseña.html")


#--------RUTA PARA CAMBIAR CONTRASEÑA--------
@app.route("/cambiar_contraseña", methods=["GET", "POST"])
def cambiar_contraseña():
    """
    Permite al usuario ingresar una nueva contraseña
    después de haber verificado su correo en la ruta anterior.
    Comprueba que ambas contraseñas coincidan y actualiza en la BD.
    """
    # Si el usuario no pasó por la recuperación, redirigir al login
    if "correo_para_recuperar" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nueva = request.form["nueva"]
        repetir = request.form["repetir"]

        # Validar que las contraseñas coincidan
        if nueva != repetir:
            return render_template("cambiar_contraseña.html", error="Las contraseñas no coinciden.")

        # Tomar correo de la sesión y encriptar nueva contraseña
        correo = session.pop("correo_para_recuperar")
        nueva_hasheada = hashlib.md5(nueva.encode()).hexdigest()

        # Actualizar contraseña en la BD
        cursor = mysql.connection.cursor()
        cursor.execute(
            "UPDATE login SET contraseña = %s WHERE correo = %s",
            (nueva_hasheada, correo),
        )
        mysql.connection.commit()
        cursor.close()

        # Redirigir al login después del cambio exitoso
        return redirect(url_for("login"))

    # Si es GET → mostrar formulario
    return render_template("cambiar_contraseña.html")


#--------LOGOUT--------
@app.route("/logout")
def logout():
    """
    Cierra la sesión del usuario actual
    y lo redirige al formulario de inicio de sesión.
    """
    session.clear()
    return redirect(url_for("login"))


#--------RUTA PRINCIPAL--------

@app.route("/")
def index():
    """
    Ruta raíz del sistema.
    Redirige directamente al login.
    """
    return redirect(url_for("login"))




# --------EJECUTAR EL SERVIDOR FLASK--------
if __name__ == '__main__':
    app.run(debug=True)
