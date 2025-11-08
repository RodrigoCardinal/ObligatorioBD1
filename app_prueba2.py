import pymysql
pymysql.install_as_MySQLdb()

# --- Importamos el conector Flask para MySQL ---
from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import hashlib
from flask import flash
import MySQLdb.cursors
from datetime import date

# --- Inicializamos la aplicación Flask ---
app = Flask(__name__)

# --- Configuramos la clave secreta de la app ---
# Se usa para encriptar la información de la sesión (por ejemplo, los datos del usuario logueado)
# En un proyecto real, esta clave debería ser más segura
app.secret_key = "clave_segura_flask123"

# --- Configuración de la conexión a la base de datos MySQL ---
app.config['MYSQL_HOST'] = 'localhost'         # Servidor de la BD
app.config['MYSQL_USER'] = 'root'              # Usuario de la BD
app.config['MYSQL_PASSWORD'] = 'rootpassword'          # Contraseña de la BD
app.config['MYSQL_DB'] = 'ObligatorioBD1'      # Nombre de la base de datos

# --- Inicializamos el objeto MySQL ---
mysql = MySQL(app)



# =====================================================
#                 RUTA DE LOGIN
# =====================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]
        contraseña_hasheada = hashlib.md5(contraseña.encode()).hexdigest()

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute("SELECT correo, contraseña FROM login WHERE correo = %s", (correo,))
        usuario = cursor.fetchone()
        cursor.close()

        if not usuario:
            return render_template("login.html", error="El correo no está registrado.")
        if usuario["contraseña"] != contraseña_hasheada:
            return render_template("login.html", error="Contraseña incorrecta.")

        session["usuario"] = {"correo": usuario["correo"]}
        return redirect(url_for("inicio"))

    return render_template("login.html")



# =====================================================
#                RUTA DE INICIO
# =====================================================
@app.route("/inicio")
def inicio():
    if "usuario" not in session:
        return redirect(url_for("login"))

    kpis = {"reservas_hoy": 0, "ocupacion": 0, "asistencias": 0, "sanciones_activas": 0}
    return render_template("inicio.html", kpis=kpis)


# =====================================================
#          HELPER PARA PROTEGER VISTAS
# =====================================================
def _require_login():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return None


# =====================================================
#          RUTAS DE SALAS
# =====================================================
@app.get("/salas")
def salas_listado():
    need = _require_login()
    if need: return need

    edificio  = request.args.get("edificio")
    tipo_sala = request.args.get("tipo_sala")
    cap_min   = request.args.get("cap_min", type=int)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # combos
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = [r["nombre_edificio"] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT tipo_sala FROM sala ORDER BY tipo_sala")
    tipos = [r["tipo_sala"] for r in cur.fetchall()]

    # query principal
    sql = "SELECT nombre_sala, edificio, capacidad, tipo_sala FROM sala WHERE 1=1"
    params = []
    if edificio:   sql += " AND edificio=%s";   params.append(edificio)
    if tipo_sala:  sql += " AND tipo_sala=%s"; params.append(tipo_sala)
    if cap_min:    sql += " AND capacidad >= %s"; params.append(cap_min)
    sql += " ORDER BY edificio, nombre_sala"

    cur.execute(sql, tuple(params))
    salas = cur.fetchall()
    cur.close()

    return render_template("salas.html", salas=salas, edificios=edificios, tipos=tipos)

@app.get("/salas/<path:edificio>/<path:nombre_sala>")
def sala_detalle(edificio, nombre_sala):
    need = _require_login()
    if need: return need
    fecha = request.args.get("fecha")  # yyyy-mm-dd (opcional)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""SELECT nombre_sala, edificio, capacidad, tipo_sala
                   FROM sala WHERE edificio=%s AND nombre_sala=%s""", (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close(); flash("Sala no encontrada.", "danger"); return redirect(url_for("salas_listado"))

    # turnos base (de tu tabla)
    cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY hora_inicio")
    horarios = cur.fetchall()

    # marcamos ocupados por hora si hay fecha
    ocupados = []
    if fecha:
        cur.execute("""SELECT t.hora_inicio
                       FROM reserva r JOIN turno t ON t.id_turno=r.id_turno
                       WHERE r.edificio=%s AND r.nombre_sala=%s AND r.fecha=%s AND r.estado IN ('activa','sin asistencia')""",
                    (edificio, nombre_sala, fecha))
        ocupados = [row["hora_inicio"].strftime("%H:%M") if hasattr(row["hora_inicio"], "strftime") else row["hora_inicio"] for row in cur.fetchall()]
    cur.close()

    # recursos: vacío por ahora
    recursos = []
    return render_template("sala.html", sala=sala, recursos=recursos, horarios=horarios, ocupados=ocupados)


@app.route("/reservas", methods=["GET"])
def reservas_listado():
    need = _require_login()
    if need: return need

    estado    = request.args.get("estado")
    fecha     = request.args.get("fecha")
    sala_like = request.args.get("sala")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    sql = """SELECT r.id_reserva, r.fecha, t.hora_inicio, t.hora_fin,
                    r.nombre_sala, r.edificio, r.estado
             FROM reserva r
             JOIN turno t ON t.id_turno = r.id_turno
             WHERE 1=1"""
    params=[]
    if estado:    sql += " AND r.estado=%s";       params.append(estado)
    if fecha:     sql += " AND r.fecha=%s";        params.append(fecha)
    if sala_like: sql += " AND r.nombre_sala LIKE %s"; params.append(f"%{sala_like}%")
    sql += " ORDER BY r.fecha DESC, t.hora_inicio"

    cur.execute(sql, tuple(params))
    reservas = cur.fetchall()
    cur.close()

    return render_template("reservas.html", reservas=reservas)


# =====================================================
#          RUTAS DE RESERVAS
# =====================================================
@app.route("/reservas/nueva", methods=["GET","POST"])
def reservas_crear():
    need = _require_login()
    if need: return need

    if request.method == "POST":
        edificio     = request.form["edificio"]
        nombre_sala  = request.form["nombre_sala"]
        fecha        = request.form["fecha"]
        id_turno     = request.form["id_turno"]
        participantes = [p.strip() for p in request.form.get("participantes","").split(",") if p.strip()]

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT COALESCE(MAX(id_reserva),0)+1 AS nxt FROM reserva")
        nxt = cur.fetchone()["nxt"]

        cur.execute("""INSERT INTO reserva (id_reserva, nombre_sala, edificio, fecha, id_turno, estado)
                       VALUES (%s,%s,%s,%s,%s,'activa')""",
                    (nxt, nombre_sala, edificio, fecha, id_turno))

        for ci in participantes:
            cur.execute("""INSERT INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
                           VALUES (%s,%s,%s,false)""",
                        (int(ci), nxt, date.today()))
        mysql.connection.commit()
        cur.close()

        flash("Reserva creada.", "success")
        return redirect(url_for("reservas_listado"))

    # GET: requiere identificar la sala
    edificio    = request.args.get("edificio")
    nombre_sala = request.args.get("nombre_sala")
    if not edificio or not nombre_sala:
        flash("Faltan parámetros de sala.", "danger")
        return redirect(url_for("salas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""SELECT nombre_sala, edificio, capacidad, tipo_sala
                   FROM sala WHERE edificio=%s AND nombre_sala=%s""",
                (edificio, nombre_sala))
    sala = cur.fetchone()
    cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY hora_inicio")
    horarios_disponibles = cur.fetchall()
    cur.close()

    return render_template("crear_reserva.html", sala=sala, horarios_disponibles=horarios_disponibles)


@app.post("/reservas/unirse")
def reservas_unirse():
    need = _require_login()
    if need: return need
    id_reserva = request.form.get("id_reserva", type=int)
    if not id_reserva:
        flash("Reserva inválida.", "danger")
        return redirect(url_for("reservas_listado"))

    # CI del usuario a partir del correo de sesión
    correo = session["usuario"]["correo"]
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT ci FROM participante WHERE email=%s", (correo,))
    row = cur.fetchone()
    if not row:
        cur.close(); flash("Tu correo no tiene CI asociado en participante.", "danger")
        return redirect(url_for("reservas_listado"))
    ci = row["ci"]

    # Evitar duplicados
    cur.execute("SELECT 1 FROM reserva_participante WHERE ci_participante=%s AND id_reserva=%s", (ci, id_reserva))
    if cur.fetchone():
        cur.close(); flash("Ya estabas unido a esa reserva.", "info")
        return redirect(url_for("reservas_listado"))

    from datetime import date
    cur.execute("""INSERT INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
                   VALUES (%s,%s,%s,false)""", (ci, id_reserva, date.today()))
    mysql.connection.commit()
    cur.close()
    flash("Te uniste a la reserva.", "success")
    return redirect(url_for("reservas_listado"))




# =====================================================
#          STUBS DE REPORTES
# =====================================================
@app.get("/reportes")
def reportes_index():
    need = _require_login()
    if need: return need

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = [r["nombre_edificio"] for r in cur.fetchall()]
    cur.close()

    kpis = {"reservas":0,"ocupacion":0,"asistencias":0,"sanciones":0}
    top_salas, top_turnos = [], []
    return render_template("reportes.html", edificios=edificios, kpis=kpis, top_salas=top_salas, top_turnos=top_turnos)

@app.get("/asistencia")
def asistencia_index():
    need = _require_login()
    if need: return need
    reservas_hoy = []
    return render_template("asistencia.html", reservas_hoy=reservas_hoy)

@app.get("/sanciones")
def sanciones_listado():
    need = _require_login()
    if need: return need
    sanciones = []
    return render_template("sanciones.html", sanciones=sanciones)

@app.route("/seguridad/cambiar-contrasena", methods=["GET","POST"])
def cambiar_contraseña():
    need = _require_login()
    if need: return need
    if request.method == "POST":
        # TODO: validar actual y actualizar hash en tabla login
        flash("Contraseña actualizada.", "success")
        return redirect(url_for("inicio"))
    return render_template("cambiar_contraseña.html")

@app.route('/recuperar-contrasena', methods=["GET","POST"])
def recuperar_contraseña():
    if request.method == "POST":
        flash("Si el correo existe, te enviamos un enlace.", "success")
        return redirect(url_for("login"))
    return render_template("recuperar_contraseña.html")


@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



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
