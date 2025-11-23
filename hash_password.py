from werkzeug.security import generate_password_hash
import pymysql


# Configura tu conexión
conn = pymysql.connect(
    host="localhost",
    user="root",
    password="tu_contraseña",
    database="ObligatorioBD1"
)
cur = conn.cursor(pymysql.cursors.DictCursor)

# ---------------------------------------------
# 1) Hashear tabla login
# ---------------------------------------------
print ("Hashear tabla login")
# Selecciona todas las contraseñas actuales
cur.execute("SELECT correo, contraseña FROM ObligatorioBD1.login")
usuarios = cur.fetchall()

for usuario in usuarios:
    contrasena_original = usuario["contraseña"]

    # Evita rehashear las que ya están hasheadas
    if not contrasena_original.startswith("scrypt:32768:8:1$"):
        nueva = generate_password_hash(contrasena_original)
        cur.execute(
            "UPDATE ObligatorioBD1.login SET contraseña = %s WHERE correo = %s",
            (nueva, usuario["correo"])
        )
        print(f"Contraseña hasheada para {usuario['correo']}")

# ---------------------------------------------
# 2) Hashear tabla invitados.contraseña_temporal
# ---------------------------------------------
print ("Hashear tabla invitados")
cur.execute("SELECT email, contraseña_temporal FROM invitados")
invitados = cur.fetchall()

for inv in invitados:
    original = inv["contraseña_temporal"]

    # evitar rehash si ya está hasheada
    if not original.startswith("scrypt:32768:8:1$"):
        nueva = generate_password_hash(original)
        cur.execute(
            "UPDATE invitados SET contraseña_temporal = %s WHERE email = %s",
            (nueva, inv["email"])
        )
        print(f"[INVITADOS] Contraseña temporal hasheada para {inv['email']}")
    else:
        print(f"[INVITADOS] Ya estaba hasheada o es NULL: {inv['email']}")

conn.commit()
conn.close()

print("Todas las contraseñas fueron rehasheadas con werkzeug.security.")





