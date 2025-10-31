# --- Importamos el conector de MySQL para poder conectarnos a la base de datos ---
import mysql.connector

# Importamos errores específicos de MySQL para poder manejarlos (por ejemplo, si ocurre un error de integridad)
from mysql.connector.errors import IntegrityError, DatabaseError


# --- Importamos las herramientas principales de Flask ---
from flask import Flask, render_template, request, redirect, url_for, session


# --- Importamos funciones propias del proyecto ---
# Estas funciones están definidas en el archivo 'conexiones.py'
# Sirven para obtener la conexión a la base de datos, con distintos permisos (admin o usuario común)
from conexiones import get_admin_connection, get_user_connection


# --- Inicializamos la aplicación Flask ---
# '__name__' le indica a Flask el punto de entrada de la aplicación
app = Flask(__name__)


# --- Configuramos la clave secreta de la app ---
# Se usa para encriptar la información de la sesión (por ejemplo, los datos del usuario logueado)
# En un proyecto real, esta clave debería ser mucho más segura y guardarse como variable de entorno
app.secret_key = "password"





# Ruta para recuperación de contraseña
@app.route('/recuperar_contraseña')
def recuperar_contraseña():
    return "Página de recuperación (en construcción)"

# Ejecutar el servidor
if __name__ == '__main__':
    app.run(debug=True)
