from flask import Flask, render_template

# Crear la aplicación Flask
app = Flask(__name__)

# Ruta principal
@app.route('/')
def home():
    return render_template('login.html')  # Muestra la página HTML

# Ruta para recuperación de contraseña
@app.route('/recuperar_contraseña')
def recuperar_contraseña():
    return "Página de recuperación (en construcción)"

# Ejecutar el servidor
if __name__ == '__main__':
    app.run(debug=True)
