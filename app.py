import os
import unicodedata
from datetime import date, datetime

import pymysql
pymysql.install_as_MySQLdb()
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.security import check_password_hash

# ---------------------------
# App & DB
# ---------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "clave_segura_flask123"

# Evitar caché en desarrollo y ver rutas reales de templates/static
app.config.update(
    DEBUG=True,
    TEMPLATES_AUTO_RELOAD=True,
    SEND_FILE_MAX_AGE_DEFAULT=0,
)
app.jinja_env.cache = {}
print("Templates dir:", os.path.abspath(app.template_folder))
print("Static dir:",    os.path.abspath(app.static_folder))

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'ObligatorioBD1'

mysql = MySQL(app)

# ---------------------------
# Helpers imágenes de salas
# ---------------------------
SALAS_REL_DIR = os.path.join('assets', 'Salas')  # relativo a /static
SALAS_ABS_DIR = os.path.join(app.static_folder, SALAS_REL_DIR)
_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}

def _slug(s: str) -> str:
    if not s:
        return ''
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ''.join(ch for ch in s.lower() if ch.isalnum())

_INDEX_IMG = {}
if os.path.isdir(SALAS_ABS_DIR):
    for fname in os.listdir(SALAS_ABS_DIR):
        base, ext = os.path.splitext(fname)
        if ext.lower() in _IMG_EXTS:
            _INDEX_IMG[_slug(base)] = fname

_ALIAS = {
    _slug('Aula Magna'):         _slug('AulaMagna'),
    _slug('Biblioteca'):         _slug('BIBLIOTECA'),
    _slug('Laboratorio'):        _slug('Laboratorio'),
    _slug('Sala de profesores'): _slug('sala-de-profesores'),
    _slug('Sala 101'):           _slug('Salon101'),
    _slug('Salón 101'):          _slug('Salon101'),
    _slug('Sala Posgrado 1'):    _slug('SalaPosgrado'),
    _slug('Lab A'):              _slug('Laboratorio'),
}

from flask import url_for

def _imagen_sala_url(nombre_sala: str):
    if not nombre_sala:
        return None
    s = _slug(nombre_sala)

    alias = _ALIAS.get(s)
    if alias and alias in _INDEX_IMG:
        return url_for('static', filename=os.path.join(SALAS_REL_DIR, _INDEX_IMG[alias]))

    if s in _INDEX_IMG:
        return url_for('static', filename=os.path.join(SALAS_REL_DIR, _INDEX_IMG[s]))

    for base_slug, real in _INDEX_IMG.items():
        if s in base_slug or base_slug in s:
            return url_for('static', filename=os.path.join(SALAS_REL_DIR, real))
    return None

@app.context_processor
def inject_now():
    return {'now': datetime.now}

def _require_login():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return None

# ---------------------------
# Auth
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = request.form["contraseña"]

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur.execute("SELECT correo, contraseña FROM login WHERE correo = %s", (correo,))
        usuario = cur.fetchone()

        if not usuario:
            cur.close()
            return render_template("login.html", error="El correo no está registrado.")

        if not check_password_hash(usuario["contraseña"], contraseña):
            cur.close()
            return render_template("login.html", error="Contraseña incorrecta.")

        #Buscar el CI del participante con ese correo
        cur.execute("SELECT ci FROM participante WHERE email = %s", (correo,))
        participante = cur.fetchone()
        cur.close()

        # Guardar en la sesión tanto correo como CI (si existe)
        session["usuario"] = {"correo": usuario["correo"],}
        if participante:
            session["user_ci"] = participante["ci"]

        return redirect(url_for("inicio"))

    return render_template("login.html")

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------------------
# Inicio
# ---------------------------
@app.get("/inicio")
def inicio():
    need = _require_login()
    if need: return need

    # KPIs simples
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT COUNT(*) c FROM reserva WHERE fecha = CURDATE()")
    reservas_hoy = (cur.fetchone() or {}).get("c", 0)

    cur.execute("SELECT COUNT(DISTINCT id_turno) t FROM turno")
    tot_turnos = (cur.fetchone() or {}).get("t", 0)

    cur.execute("SELECT COUNT(DISTINCT fecha) d FROM reserva")
    dias = (cur.fetchone() or {}).get("d", 0)
    cur.close()

    ocupacion = 0
    cur2 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur2.execute("""
        SELECT SUM(CASE WHEN rp.asistencia=1 THEN 1 ELSE 0 END) ok
        FROM reserva r LEFT JOIN reserva_participante rp ON rp.id_reserva=r.id_reserva
    """)
    asistencias = (cur2.fetchone() or {}).get("ok", 0) or 0
    cur2.close()

    if tot_turnos and dias:
        cur3 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cur3.execute("SELECT COUNT(*) c FROM reserva")
        k_res = (cur3.fetchone() or {}).get("c", 0) or 0
        cur3.close()
        ocupacion = round(100.0 * k_res / (tot_turnos * dias), 1)

    kpis = {
        "reservas_hoy": reservas_hoy or 0,
        "ocupacion": ocupacion,
        "asistencias": asistencias,
        "sanciones_activas": 0
    }
    return render_template("inicio.html", kpis=kpis)

# ---------------------------
# Salas
# ---------------------------
@app.get("/salas")
def salas_listado():
    need = _require_login()
    if need: return need

    edificio  = request.args.get("edificio")
    tipo_sala = request.args.get("tipo_sala")
    cap_min   = request.args.get("cap_min", type=int)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = [r["nombre_edificio"] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT tipo_sala FROM sala ORDER BY tipo_sala")
    tipos = [r["tipo_sala"] for r in cur.fetchall()]

    sql = "SELECT nombre_sala, edificio, capacidad, tipo_sala FROM sala WHERE 1=1"
    params = []
    if edificio:   sql += " AND edificio=%s";      params.append(edificio)
    if tipo_sala:  sql += " AND tipo_sala=%s";     params.append(tipo_sala)
    if cap_min:    sql += " AND capacidad >= %s";  params.append(cap_min)
    sql += " ORDER BY edificio, nombre_sala"

    cur.execute(sql, tuple(params))
    salas = cur.fetchall()
    for s in salas:
        s["img"] = _imagen_sala_url(s["nombre_sala"])
    cur.close()

    return render_template("salas.html", salas=salas, edificios=edificios, tipos=tipos)

@app.get("/sala")
def sala_por_query():
    need = _require_login()
    if need: return need

    edificio    = request.args.get("edificio")
    nombre_sala = request.args.get("nombre_sala")
    fecha       = request.args.get("fecha")

    if not edificio or not nombre_sala:
        flash("Faltan parámetros de sala.", "danger")
        return redirect(url_for("salas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""SELECT nombre_sala, edificio, capacidad, tipo_sala
                   FROM sala WHERE edificio=%s AND nombre_sala=%s""",
                (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash("Sala no encontrada.", "danger")
        return redirect(url_for("salas_listado"))

    sala["img"] = _imagen_sala_url(sala["nombre_sala"])

    cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY hora_inicio")
    horarios = cur.fetchall()

    ocupados = []
    if fecha:
        cur.execute("""
            SELECT TIME_FORMAT(t.hora_inicio,'%H:%i') hi
            FROM reserva r JOIN turno t ON t.id_turno=r.id_turno
            WHERE r.edificio=%s AND r.nombre_sala=%s AND r.fecha=%s
              AND r.estado IN ('activa','sin asistencia','finalizada')
        """, (edificio, nombre_sala, fecha))
        ocupados = [row["hi"] for row in cur.fetchall()]
    cur.close()

    return render_template("sala.html", sala=sala, horarios=horarios, ocupados=ocupados)

@app.get("/salas/<path:edificio>/<path:nombre_sala>")
def sala_detalle(edificio, nombre_sala):
    need = _require_login()
    if need: 
        return need

    fecha = request.args.get("fecha")  # opcional

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT nombre_sala, edificio, capacidad, tipo_sala
        FROM sala 
        WHERE edificio=%s AND nombre_sala=%s
    """, (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash("Sala no encontrada.", "danger")
        return redirect(url_for("salas_listado"))

    # --- Obtener imagen de la sala ---
    img = _imagen_sala_url(sala["nombre_sala"])

    # Turnos del día
    cur.execute("SELECT id_turno, hora_inicio, hora_fin FROM turno ORDER BY hora_inicio")
    horarios = cur.fetchall()

    # Marcamos ocupados si pasaron fecha
    ocupados = []
    if fecha:
        cur.execute("""
            SELECT TIME_FORMAT(t.hora_inicio,'%%H:%%i') AS hi
            FROM reserva r 
            JOIN turno t ON t.id_turno=r.id_turno
            WHERE r.edificio=%s AND r.nombre_sala=%s AND r.fecha=%s
              AND r.estado IN ('activa','sin asistencia','finalizada')
        """, (edificio, nombre_sala, fecha))
        ocupados = [row["hi"] for row in cur.fetchall()]

    cur.close()
    return render_template("sala.html", sala=sala, horarios=horarios, ocupados=ocupados, img = img)


# ---------------------------
# Reservas (listado, detalle, crear, unirse)
# ---------------------------
@app.get("/reservas")
def reservas_listado():
    need = _require_login()
    if need: 
        return need

    estado    = request.args.get("estado")
    fecha     = request.args.get("fecha")
    sala_like = request.args.get("sala")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    sql = """
        SELECT r.id_reserva,
               r.fecha,
               TIME_FORMAT(t.hora_inicio,'%%H:%%i') AS hora_inicio,
               TIME_FORMAT(t.hora_fin,'%%H:%%i')    AS hora_fin,
               r.nombre_sala,
               r.edificio,
               r.estado
        FROM reserva r
        JOIN turno t ON t.id_turno = r.id_turno
        WHERE 1=1   -- por qué 1=1?
    """
    params=[]
    if estado:
        sql += " AND r.estado=%s"; params.append(estado)
    if fecha:
        sql += " AND r.fecha=%s"; params.append(fecha)
    if sala_like:
        sql += " AND r.nombre_sala LIKE %s"; params.append(f"%{sala_like}%")
    sql += " ORDER BY r.fecha DESC, t.hora_inicio"

    cur.execute(sql, tuple(params))
    reservas = cur.fetchall()
    cur.close()

    return render_template("reservas.html", reservas=reservas)


@app.get("/reservas/<int:id>")
def reserva_detalle(id):
    need = _require_login()
    if need:
        return need

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # --- Obtener información principal de la reserva ---
    cur.execute("""
        SELECT r.id_reserva, r.fecha, r.estado,
               r.nombre_sala, s.edificio,
               s.capacidad, s.tipo_sala, e.direccion,
               TIME_FORMAT(t.hora_inicio,'%%H:%%i') AS hora_inicio,
               TIME_FORMAT(t.hora_fin,'%%H:%%i') AS hora_fin
        FROM reserva r
        JOIN sala  s ON s.nombre_sala = r.nombre_sala AND s.edificio = r.edificio
        JOIN edificio e on s.edificio = e.nombre_edificio 
        JOIN turno t ON t.id_turno = r.id_turno
        WHERE r.id_reserva = %s
    """, (id,))
    r = cur.fetchone()

    if not r:
        cur.close()
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    # --- Participantes de la reserva ---
    cur.execute("""
        SELECT p.ci, CONCAT(p.nombre,' ',p.apellido) AS nombre, rp.asistencia
        FROM reserva_participante rp
        JOIN participante p ON p.ci = rp.ci_participante
        WHERE rp.id_reserva = %s
        ORDER BY p.apellido, p.nombre
    """, (id,))
    participantes = cur.fetchall()


    # --- Verificar si el usuario actual forma parte de la reserva ---
    cur.execute("""
        SELECT 1
        FROM reserva_participante
        WHERE id_reserva = %s AND ci_participante = %s
    """, (id, session["user_ci"]))
    usuario_en_reserva = cur.fetchone() is not None

    cur.close()

    # --- Obtener imagen de la sala ---
    img = _imagen_sala_url(r["nombre_sala"])

    # --- Renderizar plantilla ---
    return render_template(
        "reserva_detalle.html",
        r=r,
        participantes=participantes,
        img=img,
        usuario_en_reserva=usuario_en_reserva
    )

@app.route("/baja_reserva/<int:id>", methods=["POST"])
def baja_reserva(id):
    user_ci = session.get("user_ci")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    #Ver cuántos participantes hay en la reserva
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM reserva_participante
        WHERE id_reserva = %s
    """, (id,))
    total = cur.fetchone()["total"]

    #Eliminar al usuario actual de la reserva
    cur.execute("""
        DELETE FROM reserva_participante
        WHERE id_reserva = %s AND ci_participante = %s
    """, (id, user_ci))

    #Si era el único participante → cancelar la reserva
    if total == 1:
        cur.execute("""
            UPDATE reserva
            SET estado = 'cancelada'
            WHERE id_reserva = %s
        """, (id,))

    mysql.connection.commit()
    cur.close()

    flash("Te has dado de baja de la reserva.", "success")
    return redirect(url_for("reservas_listado"))

@app.route("/reservas/nueva", methods=["GET","POST"])
def reservas_crear():
    need = _require_login()
    if need: 
        return need

    if request.method == "POST":
        edificio      = request.form.get("edificio")
        nombre_sala   = request.form.get("nombre_sala")
        fecha         = request.form.get("fecha")
        id_turno      = request.form.get("id_turno", type=int)
        clave_reserva = request.form.get("clave_reserva")

        if not (edificio and nombre_sala and fecha and id_turno and clave_reserva):
            flash("Faltan datos para crear la reserva (incluida la contraseña).", "danger")
            return redirect(url_for("reservas_crear",
                                    edificio=edificio, nombre_sala=nombre_sala, fecha=fecha))

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        # Validar disponibilidad
        cur.execute("""
            SELECT 1
            FROM reserva
            WHERE edificio=%s AND nombre_sala=%s AND fecha=%s AND id_turno=%s
              AND estado IN ('activa','sin asistencia','finalizada')
            LIMIT 1
        """, (edificio, nombre_sala, fecha, id_turno))
        if cur.fetchone():
            cur.close()
            flash("Ese turno ya fue tomado. Elegí otro.", "danger")
            return redirect(url_for("reservas_crear",
                                    edificio=edificio, nombre_sala=nombre_sala, fecha=fecha))

        # id_reserva manual
        cur.execute("SELECT COALESCE(MAX(id_reserva),0)+1 AS nxt FROM reserva")
        nxt = cur.fetchone()["nxt"]

        cur.execute("""
            INSERT INTO reserva (id_reserva, nombre_sala, edificio, fecha, id_turno, estado, clave_reserva)
            VALUES (%s,%s,%s,%s,%s,'activa',%s)
        """, (nxt, nombre_sala, edificio, fecha, id_turno, clave_reserva))

        # Auto-agregar usuario logueado si existe en participante
        cur.execute("SELECT ci FROM participante WHERE email=%s", (session["usuario"]["correo"],))
        me = cur.fetchone()
        if me:
            cur.execute("""
                INSERT IGNORE INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
                VALUES (%s,%s,%s,false)
            """, (me["ci"], nxt, date.today()))

        mysql.connection.commit()
        cur.close()

        flash("Reserva creada.", "success")
        return redirect(url_for("reserva_detalle", id=nxt))

    # GET (queda igual que lo tenías)
    edificio    = request.args.get("edificio")
    nombre_sala = request.args.get("nombre_sala")
    fecha       = request.args.get("fecha")

    if not (edificio and nombre_sala):
        flash("Faltan parámetros de sala.", "danger")
        return redirect(url_for("salas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT nombre_sala, edificio, capacidad, tipo_sala
        FROM sala
        WHERE edificio=%s AND nombre_sala=%s
    """, (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash("Sala no encontrada.", "danger")
        return redirect(url_for("salas_listado"))

    sala["img"] = _imagen_sala_url(sala["nombre_sala"])

    # Turnos libres SOLO si hay fecha
    turnos_disponibles = []
    if fecha:
        cur.execute("""
            SELECT id_turno,
                   DATE_FORMAT(hora_inicio,'%H:%i') AS hi,
                   DATE_FORMAT(hora_fin,   '%H:%i') AS hf
            FROM turno ORDER BY hora_inicio
        """)
        todos = cur.fetchall()

        cur.execute("""
            SELECT id_turno
            FROM reserva
            WHERE edificio=%s AND nombre_sala=%s AND fecha=%s
              AND estado IN ('activa','sin asistencia','finalizada')
        """, (edificio, nombre_sala, fecha))
        ocupados = {row["id_turno"] for row in cur.fetchall()}

        turnos_disponibles = [t for t in todos if t["id_turno"] not in ocupados]

    cur.close()
    return render_template("crear_reserva.html",
                           sala=sala,
                           fecha=fecha or "",
                           horarios_disponibles=turnos_disponibles)

@app.post("/reservas/unirse")
def reservas_unirse():
    need = _require_login()
    if need: 
        return need

    id_reserva    = request.form.get("id_reserva", type=int)
    clave_ingresa = request.form.get("clave_reserva")

    if not id_reserva:
        flash("Reserva inválida.", "danger")
        return redirect(url_for("reservas_listado"))

    if not clave_ingresa:
        flash("Tenés que ingresar la contraseña de la reserva.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Obtener CI del usuario logueado
    cur.execute("SELECT ci FROM participante WHERE email=%s", (session["usuario"]["correo"],))
    row = cur.fetchone()
    if not row:
        cur.close()
        flash("Tu correo no tiene CI asociado en participante.", "danger")
        return redirect(url_for("reservas_listado"))
    ci = row["ci"]


    ##Verificar si ya tiene 3 reservas activas esta semana
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM reserva_participante rp
        JOIN reserva r ON r.id_reserva = rp.id_reserva
        WHERE rp.ci_participante = %s
          AND r.estado = 'activa'
          AND YEARWEEK(r.fecha, 1) = YEARWEEK(CURDATE(), 1)
    """, (ci,))
    total = cur.fetchone()["total"]

    if total >= 3:
        cur.close()
        flash("No podés participar en más de 3 reservas activas en una misma semana.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))

    # Evitar duplicado
    cur.execute("SELECT 1 FROM reserva_participante WHERE ci_participante=%s AND id_reserva=%s",
                (ci, id_reserva))
    if cur.fetchone():
        cur.close()
        flash("Ya estabas unido a esa reserva.", "info")
        return redirect(url_for("reserva_detalle", id=id_reserva))

    # Verificar contraseña de la reserva
    cur.execute("SELECT clave_reserva FROM reserva WHERE id_reserva=%s", (id_reserva,))
    r = cur.fetchone()
    if not r:
        cur.close()
        flash("La reserva no existe.", "danger")
        return redirect(url_for("reservas_listado"))

    clave_correcta = r["clave_reserva"]

    # Si la reserva tiene clave definida, la comparamos
    if clave_correcta is not None and clave_correcta != "" and clave_ingresa != clave_correcta:
        cur.close()
        flash("Contraseña de la reserva incorrecta.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))
    
    ## No se permite tener más participantes que la capacidad de la sala.
    cur.execute("""
        SELECT COUNT(rp.ci_participante) AS actuales, s.capacidad
        FROM reserva r
        JOIN sala s 
            ON r.nombre_sala = s.nombre_sala 
        AND r.edificio = s.edificio
        LEFT JOIN reserva_participante rp 
            ON r.id_reserva = rp.id_reserva
        WHERE r.id_reserva = %s
    """, (id_reserva,))
    datos_cap = cur.fetchone()

    if datos_cap and datos_cap["actuales"] >= datos_cap["capacidad"]:
        cur.close()
        flash("La sala ya alcanzó su capacidad máxima.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))
    


    # Validación tipo de sala vs tipo participante CHAT
    # 1) Obtener tipo de sala
    cur.execute("""
        SELECT s.tipo_sala
        FROM reserva r
        JOIN sala s 
          ON r.nombre_sala = s.nombre_sala
         AND r.edificio = s.edificio
        WHERE r.id_reserva = %s
    """, (id_reserva,))
    row = cur.fetchone()
    tipo_sala = row["tipo_sala"]

    # 2) Obtener tipo real del usuario (alumno_grado, alumno_posgrado o docente)
    cur.execute("""
        SELECT pp.rol, pa.tipo
        FROM participante_programa_academico pp
        JOIN programa_academico pa
          ON pp.nombre_programa = pa.nombre_programa
        WHERE pp.ci_participante = %s
    """, (session["user_ci"],))
    roles = cur.fetchall()

    tipo_user = None

    for r in roles:
        if r["rol"] == "docente":
            tipo_user = "docente"
            break
        if r["rol"] == "alumno" and r["tipo"] == "posgrado":
            tipo_user = "alumno_posgrado"
        else:
            tipo_user = "alumno_grado"

    # 3) Reglas reales de tu institución
    compatibles = {
        "libre": ["docente", "alumno_grado", "alumno_posgrado"],
        "posgrado": ["alumno_posgrado"],
        "docente": ["docente"]
    }

    # 4) Validar compatibilidad
    if tipo_user not in compatibles.get(tipo_sala, []):
        flash("No estás autorizado para reservar este tipo de sala.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))
    

##  Evitar reservas simultáneas 
# Obtener fecha y turno de la reserva actual
    cur.execute("""
        SELECT fecha, id_turno
        FROM reserva
        WHERE id_reserva = %s
    """, (id_reserva,))
    info_res = cur.fetchone()

    fecha_res = info_res["fecha"]
    turno_res = info_res["id_turno"]

    # Verificar si el usuario ya tiene una reserva en esa fecha y turno
    cur.execute("""
        SELECT 1
        FROM reserva_participante rp
        JOIN reserva r ON r.id_reserva = rp.id_reserva
        WHERE rp.ci_participante = %s
        AND r.fecha = %s
        AND r.id_turno = %s
        AND r.estado IN ('activa', 'sin asistencia')
    """, (session["user_ci"], fecha_res, turno_res))

    choque = cur.fetchone()

    if choque:
        flash("Ya tenés una reserva en este mismo horario.", "danger")
        return redirect(url_for("reserva_detalle", id=id_reserva))
    

    # Si la clave es correcta (o la reserva no tiene clave), insertamos
    cur.execute("""
        INSERT INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
        VALUES (%s,%s,%s,false)
    """, (ci, id_reserva, date.today()))
    mysql.connection.commit()
    cur.close()

    flash("Te uniste a la reserva.", "success")
    return redirect(url_for("reserva_detalle", id=id_reserva))



# ---------------------------
# Asistencia (hoy)
# ---------------------------
@app.route("/asistencia", methods=["GET"])
def asistencia_index():
    need = _require_login()
    if need:
        return need

    correo = session["usuario"]["correo"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT ci FROM participante WHERE email=%s", (correo,))
    row = cur.fetchone()
    if not row:
        cur.close()
        flash("Tu correo no tiene CI asociado en participante.", "danger")
        return render_template("asistencia.html", reservas_hoy=[])

    ci = row["ci"]

    sql = """
        SELECT r.id_reserva AS id,
               r.nombre_sala AS sala,
               CONCAT(TIME_FORMAT(t.hora_inicio,'%%H:%%i'),' - ',TIME_FORMAT(t.hora_fin,'%%H:%%i')) AS hora,
               MAX(CASE WHEN rp.ci_participante=%s THEN rp.asistencia ELSE NULL END) AS asistio
        FROM reserva r
        JOIN turno t ON t.id_turno = r.id_turno
        LEFT JOIN reserva_participante rp ON rp.id_reserva = r.id_reserva
        WHERE r.fecha = CURDATE()
          AND EXISTS(SELECT 1 FROM reserva_participante rp2 WHERE rp2.id_reserva=r.id_reserva AND rp2.ci_participante=%s)
        GROUP BY r.id_reserva, r.nombre_sala, t.hora_inicio, t.hora_fin
        ORDER BY t.hora_inicio
    """
    cur.execute(sql, (ci, ci))
    reservas_hoy = cur.fetchall()
    cur.close()

    return render_template("asistencia.html", reservas_hoy=reservas_hoy)


@app.post("/asistencia/marcar")
def asistencia_marcar():
    need = _require_login()
    if need: return need

    id_reserva = request.form.get("id_reserva", type=int)
    asistio    = request.form.get("asistio") == "1"

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Solo se puede marcar el MISMO día
    cur.execute("SELECT fecha FROM reserva WHERE id_reserva=%s", (id_reserva,))
    row = cur.fetchone()
    if not row or str(row["fecha"]) != str(date.today()):
        cur.close()
        flash("La asistencia solo se puede marcar el mismo día de la reserva.", "warning")
        return redirect(url_for("asistencia_index"))

    cur.execute("SELECT ci FROM participante WHERE email=%s", (session["usuario"]["correo"],))
    me = cur.fetchone()
    if not me:
        cur.close()
        flash("No se pudo marcar asistencia.", "danger")
        return redirect(url_for("asistencia_index"))

    cur.execute("""
        UPDATE reserva_participante
        SET asistencia=%s
        WHERE ci_participante=%s AND id_reserva=%s
    """, (asistio, me["ci"], id_reserva))
    mysql.connection.commit()
    cur.close()

    flash("Asistencia actualizada.", "success")
    return redirect(url_for("asistencia_index"))



# ---------------------------
# Sanciones
# ---------------------------
@app.get("/sanciones")
def sanciones_listado():
    need = _require_login()
    if need: return need

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
                SELECT p.ci,
                       CONCAT(p.nombre, ' ', p.apellido) nombre,
                       s.fecha_inicio                    desde,
                       s.fecha_fin                       hasta
                FROM sancion_participante s
                         JOIN participante p ON p.ci = s.ci_participante
                ORDER BY s.fecha_inicio DESC
                """)

    hoy = date.today()
    sanciones = []
    for r in cur.fetchall():
        desde = r["desde"]
        hasta = r["hasta"]
        sanciones.append({
            "ci": r["ci"],
            "nombre": r["nombre"],
            "motivo": "No asistencia",
            "desde": desde,
            "hasta": hasta,
            "activa": desde <= hoy <= hasta
        })

    cur.close()
    return render_template("sanciones.html", sanciones=sanciones)

# ---------------------------
# Reportes
# ---------------------------
@app.get("/reportes")
def reportes_index():
    need = _require_login()
    if need:
        return need

    # ---- Filtros del formulario ----
    tipo  = request.args.get("tipo_reporte", "uso_salas")
    desde = request.args.get("desde")
    hasta = request.args.get("hasta")
    edif  = request.args.get("edificio")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Combo de edificios
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = [r["nombre_edificio"] for r in cur.fetchall()]

    # --- Filtros comunes para consultas basadas en reserva r ---
    filtros = []
    params  = []
    if desde:
        filtros.append("r.fecha >= %s")
        params.append(desde)
    if hasta:
        filtros.append("r.fecha <= %s")
        params.append(hasta)
    if edif:
        filtros.append("r.edificio = %s")
        params.append(edif)

    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""

    columnas, datos = [], []

    if tipo == "uso_salas":
        columnas = ["Sala", "Edificio", "Reservas"]
        cur.execute(f"""
            SELECT r.nombre_sala, r.edificio, COUNT(*) AS CantReservas
            FROM reserva r
            {where}
            GROUP BY r.nombre_sala, r.edificio
            ORDER BY CantReservas DESC, r.edificio, r.nombre_sala
            LIMIT 10
        """, tuple(params))
        rows = cur.fetchall()
        datos = [[x["nombre_sala"], x["edificio"], x["CantReservas"]] for x in rows]

    # ============================================================
    # 2) Asistencias por reserva (YA LO TENÍAS)
    # ============================================================
    elif tipo == "asistencias":
        columnas = ["Fecha", "Reserva", "Participantes", "Asistieron", "Tasa %"]
        cur.execute(f"""
            SELECT r.id_reserva, r.fecha,
                   COUNT(rp.ci_participante) AS tot,
                   SUM(CASE WHEN rp.asistencia=1 THEN 1 ELSE 0 END) AS ok
            FROM reserva r
            LEFT JOIN reserva_participante rp ON rp.id_reserva=r.id_reserva
            {where}
            GROUP BY r.id_reserva, r.fecha
            ORDER BY r.fecha DESC, r.id_reserva DESC
            LIMIT 50
        """, tuple(params))
        rows = cur.fetchall()
        for x in rows:
            tot = x["tot"] or 0
            ok  = x["ok"] or 0
            tasa = round(ok * 100.0 / (tot or 1), 1)
            datos.append([str(x["fecha"]), x["id_reserva"], tot, ok, tasa])

    # ============================================================
    # 3) Listado de sanciones (YA LO TENÍAS)
    # ============================================================
    elif tipo == "sanciones":
        columnas = ["CI", "Nombre", "Desde", "Hasta"]
        cur.execute("""
            SELECT p.ci, CONCAT(p.nombre,' ',p.apellido) AS nombre,
                   s.fecha_inicio, s.fecha_fin
            FROM sancion_participante s
            JOIN participante p ON p.ci = s.ci_participante
            ORDER BY s.fecha_inicio DESC
            LIMIT 100
        """)
        rows = cur.fetchall()
        datos = [[x["ci"], x["nombre"], str(x["fecha_inicio"]), str(x["fecha_fin"])] for x in rows]

    # ============================================================
    # 4) Promedio de participantes por sala
    #    (consulta: "Promedio de participantes por sala")
    # ============================================================
    elif tipo == "prom_participantes":
        columnas = ["Sala", "Promedio de participantes"]
        cur.execute("""
            SELECT sub.nombre_sala,
                   ROUND(AVG(sub.cant_participantes),2) AS PromParticipantes
            FROM (
                SELECT r.id_reserva,
                       r.nombre_sala,
                       COUNT(rp.ci_participante) AS cant_participantes
                FROM reserva r
                LEFT JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                GROUP BY r.id_reserva, r.nombre_sala
            ) sub
            GROUP BY sub.nombre_sala
            ORDER BY PromParticipantes DESC, sub.nombre_sala
        """)
        rows = cur.fetchall()
        datos = [[x["nombre_sala"], x["PromParticipantes"]] for x in rows]

    # ============================================================
    # 5) Cantidad de reservas por carrera y facultad
    # ============================================================
    elif tipo == "reservas_carrera":
        columnas = ["Facultad", "Carrera", "Reservas"]
        cur.execute("""
            SELECT f.nombre AS Facultad,
                   pa.nombre_programa AS Carrera,
                   COUNT(r.id_reserva) AS CantReservas
            FROM facultad f
            LEFT JOIN programa_academico pa
                   ON pa.id_facultad = f.id_facultad
            LEFT JOIN participante_programa_academico ppa
                   ON pa.nombre_programa = ppa.nombre_programa
            LEFT JOIN reserva_participante rp
                   ON ppa.ci_participante = rp.ci_participante
            LEFT JOIN reserva r
                   ON r.id_reserva = rp.id_reserva
            GROUP BY f.nombre, pa.nombre_programa
            ORDER BY Facultad, Carrera
        """)
        rows = cur.fetchall()
        datos = [[x["Facultad"], x["Carrera"], x["CantReservas"]] for x in rows]

    # ============================================================
    # 6) Reservas y asistencias por rol (alumno/profesor, grado/posgrado)
    # ============================================================
    elif tipo == "reservas_rol":
        columnas = ["Rol", "Reservas", "Asistencias"]
        cur.execute("""
            SELECT ppa.rol,
                   COUNT(rp.id_reserva) AS CantReservas,
                   COUNT(IF(rp.asistencia = TRUE, 1, NULL)) AS CantAsistencias
            FROM participante_programa_academico ppa
            JOIN reserva_participante rp
                 ON ppa.ci_participante = rp.ci_participante
            GROUP BY ppa.rol
        """)
        rows = cur.fetchall()
        datos = [[x["rol"], x["CantReservas"], x["CantAsistencias"]] for x in rows]

    # ============================================================
    # 7) Cantidad de sanciones por rol (alumno/profesor)
    # ============================================================
    elif tipo == "sanciones_rol":
        columnas = ["Rol", "Personas con sanciones"]
        cur.execute("""
            SELECT ppa.rol,
                   COUNT(DISTINCT sp.ci_participante) AS CantSanciones
            FROM participante_programa_academico ppa
            JOIN sancion_participante sp
                 ON ppa.ci_participante = sp.ci_participante
            GROUP BY ppa.rol
        """)
        rows = cur.fetchall()
        datos = [[x["rol"], x["CantSanciones"]] for x in rows]

    # ============================================================
    # 8) Porcentaje de reservas utilizadas vs. no utilizadas
    # ============================================================
    elif tipo == "porcentaje_uso":
        columnas = ["Estado", "% Reservas"]
        cur.execute("""
            SELECT
                CASE
                    WHEN estado IN ('activa','finalizada') THEN 'Utilizadas'
                    ELSE 'No utilizadas'
                END AS EstadoReserva,
                ROUND(
                    COUNT(*) * 100.0 / (SELECT COUNT(*) FROM reserva),
                    1
                ) AS PorcentajeReservas
            FROM reserva
            GROUP BY EstadoReserva
        """)
        rows = cur.fetchall()
        datos = [[x["EstadoReserva"], x["PorcentajeReservas"]] for x in rows]

    # ============================================================
    # 9) Reservas por turno (todas las reservas por franja horaria)
    # ============================================================
    elif tipo == "reservas_turno":
        columnas = ["Turno", "Reservas"]
        cur.execute("""
            SELECT CONCAT(DATE_FORMAT(t.hora_inicio,'%H:%i'),' - ',
                          DATE_FORMAT(t.hora_fin,'%H:%i')) AS turno,
                   COUNT(r.id_reserva) AS CantReservas
            FROM turno t
            LEFT JOIN reserva r ON t.id_turno = r.id_turno
            GROUP BY t.hora_inicio, t.hora_fin
            ORDER BY t.hora_inicio
        """)
        rows = cur.fetchall()
        datos = [[x["turno"], x["CantReservas"]] for x in rows]

    # ============================================================
    # 10) Reservas del segundo semestre 2025
    # ============================================================
    elif tipo == "reservas_semestre":
        columnas = ["ID", "Sala", "Edificio", "Fecha", "Turno"]
        cur.execute("""
            SELECT r.id_reserva,
                   r.nombre_sala,
                   r.edificio,
                   r.fecha,
                   CONCAT(DATE_FORMAT(t.hora_inicio,'%H:%i'),' - ',
                          DATE_FORMAT(t.hora_fin,'%H:%i')) AS turno
            FROM reserva r
            JOIN turno t ON t.id_turno = r.id_turno
            WHERE r.fecha BETWEEN '2025-08-12' AND '2025-12-05'
            ORDER BY r.fecha, t.hora_inicio
        """)
        rows = cur.fetchall()
        datos = [[x["id_reserva"], x["nombre_sala"], x["edificio"],
                  str(x["fecha"]), x["turno"]] for x in rows]

    # ============================================================
    # 11) Participantes con cantidad de sanciones
    # ============================================================
    elif tipo == "participantes_sanciones":
        columnas = ["CI", "Nombre", "Apellido", "Sanciones"]
        cur.execute("""
            SELECT p.nombre, p.apellido, p.ci,
                   COUNT(*) AS CantSanciones
            FROM participante p
            JOIN sancion_participante sp
                 ON sp.ci_participante = p.ci
            GROUP BY p.nombre, p.apellido, p.ci
            ORDER BY CantSanciones DESC
        """)
        rows = cur.fetchall()
        datos = [[x["ci"], x["nombre"], x["apellido"], x["CantSanciones"]] for x in rows]

    # ============================================================
    # KPIs generales (igual que antes)
    # ============================================================
    cur.execute(f"SELECT COUNT(*) AS c FROM reserva r {where}", tuple(params))
    k_res = (cur.fetchone() or {}).get("c", 0) or 0

    cur.execute("SELECT COUNT(*) AS t FROM turno")
    tot_turnos = (cur.fetchone() or {}).get("t", 0) or 0

    cur.execute(f"SELECT COUNT(DISTINCT r.fecha) AS d FROM reserva r {where}", tuple(params))
    dias = (cur.fetchone() or {}).get("d", 0) or 0

    ocupacion = 0
    if tot_turnos and dias:
        ocupacion = round(100.0 * k_res / (tot_turnos * dias), 1)

    cur.execute(f"""
        SELECT SUM(CASE WHEN rp.asistencia=1 THEN 1 ELSE 0 END) AS ok
        FROM reserva r
        LEFT JOIN reserva_participante rp ON rp.id_reserva=r.id_reserva
        {where}
    """, tuple(params))
    k_ok = (cur.fetchone() or {}).get("ok", 0) or 0

    cur.execute("""
        SELECT COUNT(*) AS c FROM sancion_participante
        WHERE CURDATE() BETWEEN fecha_inicio AND fecha_fin
    """)
    k_sanc = (cur.fetchone() or {}).get("c", 0) or 0

    # Top salas y top turnos (como ya tenías)
    cur.execute(f"""
        SELECT r.nombre_sala AS sala,
               r.edificio,
               COUNT(*) AS count
        FROM reserva r
        {where}
        GROUP BY r.nombre_sala, r.edificio
        ORDER BY count DESC, r.edificio, r.nombre_sala
        LIMIT 10
    """, tuple(params))
    top_salas = cur.fetchall()

    cur.execute(f"""
        SELECT CONCAT(DATE_FORMAT(t.hora_inicio,'%%H:%%i'),' - ',
                      DATE_FORMAT(t.hora_fin,'%%H:%%i')) AS turno,
               COUNT(*) AS count
        FROM reserva r
        JOIN turno t ON t.id_turno = r.id_turno
        {where}
        GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
        ORDER BY count DESC, t.hora_inicio
        LIMIT 10
    """, tuple(params))
    top_turnos = cur.fetchall()

    cur.close()

    kpis = {
        "reservas": k_res,
        "ocupacion": ocupacion,
        "asistencias": k_ok,
        "sanciones": k_sanc,
    }

    return render_template(
        "reportes.html",
        edificios=edificios,
        kpis=kpis,
        columnas=columnas,
        datos=datos,
        top_salas=top_salas,
        top_turnos=top_turnos,
        tipo_reporte=tipo,   # se lo mandamos al template
        desde=desde,
        hasta=hasta,
        edif=edif,
    )


# ---------------------------
# Recuperar contraseña (el login lo linkea)
# ---------------------------
@app.route('/recuperar-contrasena', methods=["GET", "POST"])
def recuperar_contraseña():
    if request.method == "POST":
        flash("Si el correo existe, te enviamos un enlace.", "success")
        return redirect(url_for("login"))
    return render_template("recuperar_contraseña.html")

# --- Compat: enlaces antiguos a cambiar_contraseña ---
@app.get("/seguridad/cambiar-contrasena", endpoint="cambiar_contraseña")
def cambiar_contraseña_legacy():
    # Redirigimos a Recuperar contraseña para mantener compatibilidad
    return redirect(url_for("recuperar_contraseña"))


# ---------------------------
# Root
# ---------------------------
@app.route("/")
def index():
    return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)

