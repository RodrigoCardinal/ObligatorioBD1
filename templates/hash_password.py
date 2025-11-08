
"""
from werkzeug.security import generate_password_hash
import pymysql

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="rootpassword",
    database="ObligatorioBD1"
)
cur = conn.cursor(pymysql.cursors.DictCursor)

cur.execute("SELECT correo, contraseña FROM ObligatorioBD1.login")
usuarios = cur.fetchall()

for usuario in usuarios:
    plano_o_hash = usuario["contraseña"] or ""
    if not plano_o_hash.startswith("pbkdf2:sha256:"):
        nuevo = generate_password_hash(plano_o_hash)
        cur.execute(
            "UPDATE ObligatorioBD1.login SET contraseña=%s WHERE correo=%s",
            (nuevo, usuario["correo"])
        )
        print(f"Contraseña rehasheada para {usuario['correo']}")

conn.commit()
conn.close()
print("Todas las contraseñas fueron rehasheadas con werkzeug.security.")
"""

# rehash_safe.py
from werkzeug.security import generate_password_hash
import pymysql

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="rootpassword",
    database="ObligatorioBD1",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
cur = conn.cursor()

cur.execute("SELECT DATABASE() AS db")
print("Conectado a DB:", cur.fetchone()["db"])

cur.execute("SELECT correo, contraseña FROM login ORDER BY correo")
usuarios = cur.fetchall()

saltados = 0
actualizados = 0
for u in usuarios:
    correo = (u["correo"] or "").strip()
    pwd    = (u["contraseña"] or "").strip()

    # Ya parece hash? (prefijos comunes)
    lower = pwd.lower()
    if lower.startswith("pbkdf2:sha256") or lower.startswith("scrypt:"):
        print(f"[OK] ya hasheada: {correo}")
        saltados += 1
        continue

    # Heurística extra: si es muy largo o contiene '$', tratamos como hash y no tocamos
    if len(pwd) >= 60 or "$" in pwd:
        print(f"[SKIP] formato desconocido pero largo/hashy: {correo} (len={len(pwd)})")
        saltados += 1
        continue

    # Parece texto plano -> hashear
    nuevo = generate_password_hash(pwd)  # pbkdf2:sha256 por defecto
    cur.execute("UPDATE login SET contraseña=%s WHERE correo=%s", (nuevo, correo))
    print(f"[UPDATE] rehasheada: {correo}")
    actualizados += 1

conn.commit()
cur.close()
conn.close()

print(f"Listo. {actualizados} actualizados, {saltados} saltados.")
