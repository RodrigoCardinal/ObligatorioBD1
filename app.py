from flask import Flask, render_template

# Crear la aplicación Flask
app = Flask(__name__)

# Ruta principal
@app.route('/')
def home():
    return render_template('index.html')  # Muestra la página HTML

# Ejecutar el servidor
if __name__ == '__main__':
    app.run(debug=True)

# Nota: Asegúrate de tener un archivo 'index.html' en una carpeta llamada 'templates' en el mismo directorio que este script.