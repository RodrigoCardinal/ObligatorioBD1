from werkzeug.security import generate_password_hash
import pymysql

# Configura tu conexión
conn = pymysql.connect(
    host="localhost",
    user="root",
    password="tu_contraseña",  # <-- pon aquí la que usas
    database="ObligatorioBD1"
)
cur = conn.cursor(pymysql.cursors.DictCursor)

# Selecciona todas las contraseñas actuales
cur.execute("SELECT correo, contraseña FROM ObligatorioBD1.login")
usuarios = cur.fetchall()

for usuario in usuarios:
    contrasena_original = usuario["contraseña"]

    # Evita rehashear las que ya están hasheadas
    if not contrasena_original.startswith("pbkdf2:sha256:"):
        nueva = generate_password_hash(contrasena_original)
        cur.execute(
            "UPDATE ObligatorioBD1.login SET contraseña = %s WHERE correo = %s",
            (nueva, usuario["correo"])
        )
        print(f"Contraseña rehasheada para {usuario['correo']}")

conn.commit()
conn.close()

print("Todas las contraseñas fueron rehasheadas con werkzeug.security.")