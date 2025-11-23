import os
import unicodedata
from datetime import date, datetime, timedelta
import pymysql
pymysql.install_as_MySQLdb()
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors
from werkzeug.security import check_password_hash, generate_password_hash
from hashids import Hashids

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
print("Static dir:", os.path.abspath(app.static_folder))

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'tu_contraseña'
app.config['MYSQL_DB'] = 'ObligatorioBD1'

mysql = MySQL(app)
hashids = Hashids(salt=app.secret_key, min_length=8)

# ---------------------------
# Helpers imágenes de salas
# ---------------------------
SALAS_REL_DIR = "assets/Salas"
SALAS_ABS_DIR = os.path.join(app.static_folder, "assets", "Salas")
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
    _slug('Aula Magna'): _slug('AulaMagna'),
    _slug('Biblioteca'): _slug('BIBLIOTECA'),
    _slug('Laboratorio'): _slug('Laboratorio'),
    _slug('Sala Docente 2'): _slug('sala-de-profesores'),
    _slug('Sala 101'): _slug('Salon101'),
    _slug('Salón 101'): _slug('Salon101'),
    _slug('Sala Posgrado 1'): _slug('SalaPosgrado'),
    _slug('Lab A'): _slug('Laboratorio'),
}

def _imagen_sala_url(nombre_sala: str):
    if not nombre_sala:
        return None

    s = _slug(nombre_sala)

    alias = _ALIAS.get(s)
    if alias and alias in _INDEX_IMG:
        return url_for('static', filename=f"{SALAS_REL_DIR}/{_INDEX_IMG[alias]}")

    if s in _INDEX_IMG:
        return url_for('static', filename=f"{SALAS_REL_DIR}/{_INDEX_IMG[s]}")

    for base_slug, real in _INDEX_IMG.items():
        if s in base_slug or base_slug in s:
            return url_for('static', filename=f"{SALAS_REL_DIR}/{real}")

    return None

def hash_id(id_reserva):
    """Convierte un ID numérico a hash"""
    return hashids.encode(id_reserva)

def unhash_id(hashed_id):
    """Convierte un hash de vuelta a ID numérico"""
    try:
        decoded = hashids.decode(hashed_id)
        return decoded[0] if decoded else None
    except:
        return None

@app.context_processor
def utility_processor():
    return dict(hash_id=hash_id)

@app.context_processor
def inject_now():
    return {'now': datetime.now}


def _require_login():
    if "usuario" not in session:
        return redirect(url_for("login"))
    return None

# ============================================================
# CONDICIONALES al crear o unirse a una reserva
# ============================================================
def verificador(edificio, nombre_sala, fecha, id_turno, id_reserva=None, clave_ingresa=None):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # ============================================================
    # OBTENER CI DEL USUARIO
    # ============================================================
    ci = session["usuario"]["ci"]
    if ci is None:
        flash("Tu correo no tiene CI asociado en participante.", "danger")
        return redirect(url_for("reservas_listado"))

    # ========================================================================
    # No permitir reservar o unirse a una reserva si tiene una sanción activa
    # ========================================================================
    cur.execute("""
                SELECT fecha_inicio, fecha_fin
                FROM sancion_participante
                WHERE ci_participante = %s
                  AND CURDATE() BETWEEN fecha_inicio and fecha_fin
                """, (ci,))
    hay_sancion = cur.fetchone()

    if hay_sancion:
        fecha_fin = hay_sancion["fecha_fin"]
        cur.close()
        flash(f"Usted tiene una sanción activa hasta {fecha_fin}.", "danger")
        return redirect(url_for("reservas_listado"))

    # ============================================================
    # VALIDAR TIPO DE SALA vs TIPO DE USUARIO (crear o unirse)
    # ============================================================

    # --- Obtener tipo de sala ---
    cur.execute("""
                SELECT tipo_sala
                FROM sala
                WHERE nombre_sala = %s
                  AND edificio = %s
                """, (nombre_sala, edificio))
    row = cur.fetchone()

    if not row:
        cur.close()
        flash("No se pudo determinar el tipo de sala.", "danger")
        return redirect(url_for("reservas_listado"))

    tipo_sala = row["tipo_sala"]

    # --- Obtener roles del usuario ---
    cur.execute("""
                SELECT pp.rol, pa.tipo
                FROM participante_programa_academico pp
                         JOIN programa_academico pa
                              ON pp.nombre_programa = pa.nombre_programa
                WHERE pp.ci_participante = %s
                """, (ci,))
    roles = cur.fetchall()

    # --- Determinar tipo de usuario ---
    es_docente = any(r["rol"] == "docente" for r in roles)
    es_posgrado = any(r["rol"] == "alumno" and r["tipo"] == "posgrado" for r in roles)

    if es_docente:
        tipo_user = "docente"
    elif es_posgrado:
        tipo_user = "alumno_posgrado"
    else:
        tipo_user = "alumno_grado"

    # --- Compatibilidades ---
    compatibles = {
        "libre": ["docente", "alumno_grado", "alumno_posgrado"],
        "posgrado": ["alumno_posgrado"],
        "docente": ["docente"]
    }

    if tipo_user not in compatibles.get(tipo_sala, []):
        cur.close()
        flash("No estás autorizado para usar este tipo de sala.", "danger")

        if id_reserva is None:
            return redirect(url_for(
                "reservas_crear",
                edificio=edificio,
                nombre_sala=nombre_sala,
                fecha=fecha
            ))
        else:
            return redirect(url_for("reserva_detalle", hashed_id=id_reserva))

    # ============================================================
    #  VALIDACIÓN OBLIGATORIA: NO PERMITIR RESERVAS PASADAS
    # ============================================================
    if id_reserva is not None:
        cur.execute("""
                    SELECT r.fecha, t.hora_inicio
                    FROM reserva r
                             JOIN turno t ON r.id_turno = t.id_turno
                    WHERE r.id_reserva = %s
                    """, (id_reserva,))
        data = cur.fetchone()

        if not data:
            cur.close()
            flash("La reserva no existe.", "danger")
            return redirect(url_for("reservas_listado"))

        fecha_reserva = data["fecha"]
        hora_inicio = data["hora_inicio"]

        # ============================================================
        # SI ES CREAR RESERVA -> FECHA Y HORA VIENEN DEL FORMULARIO
        # ============================================================
    else:
        # fecha viene como string: "2025-11-14"
        fecha_reserva = datetime.strptime(fecha, "%Y-%m-%d").date()

        # obtener hora desde id_turno
        cur.execute("SELECT hora_inicio FROM turno WHERE id_turno = %s", (id_turno,))
        row = cur.fetchone()

        if not row:
            cur.close()
            flash("El turno no existe.", "danger")
            return redirect(url_for("reservas_listado"))

        hora_inicio = row["hora_inicio"]

    # ============================================================
    # Normalizar hora_inicio
    # ============================================================
    if isinstance(hora_inicio, str):
        hora_inicio = datetime.strptime(hora_inicio, "%H:%M:%S").time()

    elif isinstance(hora_inicio, timedelta):
        hora_inicio = (datetime.min + hora_inicio).time()

    # ============================================================
    # PROHIBIR RESERVAS PASADAS
    # ============================================================
    fecha_hora_reserva = datetime.combine(fecha_reserva, hora_inicio)
    ahora = datetime.now()

    if fecha_hora_reserva < ahora:
        cur.close()
        flash("No puedes crear ni unirte a una reserva pasada.", "danger")

        if id_reserva:
            return redirect(url_for("reserva_detalle", hashed_id=id_reserva))
        else:
            return redirect(url_for("reservas_crear"))

    # ============================================================
    # VALIDACIONES COMUNES: turnos, límite semanal y diario
    # ============================================================

    # --- 1) Turno ya tomado (solo al CREAR)
    if id_reserva is None:
        cur.execute("""
                    SELECT 1
                    FROM reserva
                    WHERE edificio = %s
                      AND nombre_sala = %s
                      AND fecha = %s
                      AND id_turno = %s
                      AND estado IN ('activa', 'sin asistencia', 'finalizada')
                    LIMIT 1
                    """, (edificio, nombre_sala, fecha, id_turno))

        if cur.fetchone():
            cur.close()
            flash("Ese turno ya fue tomado. Elegí otro.", "danger")
            return redirect(url_for(
                "reservas_crear",
                edificio=edificio,
                nombre_sala=nombre_sala,
                fecha=fecha
            ))
    # Limitaciones para estudiantes de grado
    if tipo_user == "alumno_grado":
        # --- 2) Límite semanal (máximo 3 activas + sin asistencia)
        # print("DEBUG — CI:", ci)
        # print("DEBUG — Fecha nueva reserva:", fecha)

        cur.execute("""
                    SELECT r.id_reserva, r.fecha, r.estado
                    FROM reserva r
                             JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                    WHERE rp.ci_participante = %s
                    ORDER BY r.fecha DESC
                    """, (ci,))
        # print("DEBUG — Todas sus reservas:", cur.fetchall())

        cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM reserva r
                             JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                    WHERE rp.ci_participante = %s
                      AND r.estado = 'activa'
                      AND YEARWEEK(r.fecha, 1) = YEARWEEK(%s, 1)
                    """, (ci, fecha))

        row = cur.fetchone()
        total = row["total"]

        if total >= 3:
            cur.close()
            flash("No podés participar en más de 3 reservas activas en la semana.", "danger")

            if id_reserva is None:  # creando
                return redirect(url_for("reservas_crear",
                                        edificio=edificio,
                                        nombre_sala=nombre_sala,
                                        fecha=fecha))
            else:  # uniéndose
                return redirect(url_for("reserva_detalle", hashed_id=id_reserva))

        # --- 3) Límite diario: máximo 2 reservas
        cur.execute("""
                    SELECT COUNT(*) AS total
                    FROM reserva r
                             JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                    WHERE rp.ci_participante = %s
                      AND r.estado = 'activa'
                      AND r.fecha = %s
                    """, (ci, fecha))

        row = cur.fetchone()
        total = row["total"] if row else 0

        if total >= 2:
            cur.close()
            flash("No podés participar en más de 2 reservas por día.", "danger")
            if id_reserva is None:  # creando
                return redirect(url_for("reservas_crear",
                                        edificio=edificio,
                                        nombre_sala=nombre_sala,
                                        fecha=fecha))
            else:  # uniéndose
                return redirect(url_for("reserva_detalle", hashed_id=id_reserva))

    # ============================================================
    # VALIDACIONES EXTRA AL UNIRSE (id_reserva != None)
    # ============================================================
    if id_reserva is not None:
        print("### Verificador EJECUTADO ###")

        # --- A) Verificar existencia de la reserva ---
        cur.execute("SELECT clave_reserva FROM reserva WHERE id_reserva=%s",
                    (id_reserva,))
        r = cur.fetchone()

        if not r:
            cur.close()
            flash("La reserva no existe.", "danger")
            return redirect(url_for("reservas_listado"))

        clave_correcta = r["clave_reserva"]

        # --- Validar clave ---
        if not check_password_hash(clave_correcta, clave_ingresa):
            cur.close()
            flash("Tenés que ingresar la contraseña de la reserva.", "danger")
            return redirect(url_for("reserva_detalle", hahed_id=id_reserva))


        # --- Verificar capacidad ---
        cur.execute("""
                    SELECT COUNT(rp.ci_participante) AS actuales, s.capacidad
                    FROM reserva r
                             JOIN sala s ON r.nombre_sala = s.nombre_sala
                        AND r.edificio = s.edificio
                             LEFT JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                    WHERE r.id_reserva = %s
                    """, (id_reserva,))
        datos_cap = cur.fetchone()

        if datos_cap["actuales"] >= datos_cap["capacidad"]:
            cur.close()
            flash("La sala ya alcanzó su capacidad máxima.", "danger")
            return redirect(url_for("reserva_detalle", hashed_id=id_reserva))

        # --- Evitar reservas simultáneas ---
        cur.execute("""
                    SELECT fecha, id_turno
                    FROM reserva
                    WHERE id_reserva = %s
                    """, (id_reserva,))
        info_res = cur.fetchone()

        cur.execute("""
                    SELECT 1
                    FROM reserva_participante rp
                             JOIN reserva r ON r.id_reserva = rp.id_reserva
                    WHERE rp.ci_participante = %s
                      AND r.fecha = %s
                      AND r.id_turno = %s
                      AND r.estado IN ('activa', 'sin asistencia')
                    """, (ci, info_res["fecha"], info_res["id_turno"]))

        if cur.fetchone():
            cur.close()
            flash("Ya tenés una reserva en este mismo horario.", "danger")
            return redirect(url_for("reserva_detalle", hashed_id=id_reserva))


    # --- si no hay problemas, devolvemos True
    cur.close()
    return True

# ---------------------------
# Autenticador
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = request.form.get("contraseña")
        rol_seleccionado = request.form.get("rol_admin")

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        #si viene de la selección de rol (ya validado previamente)
        if rol_seleccionado and session.get("admin_validado") == correo:
            # Recuperar datos del usuario ya validado
            cur.execute("""
                SELECT correo, es_administrador 
                FROM login 
                WHERE correo = %s
            """, (correo,))
            usuario = cur.fetchone()

            # Buscar CI del participante
            cur.execute("SELECT ci FROM participante WHERE email = %s", (correo,))
            participante = cur.fetchone()
            ci = participante["ci"] if participante else None
            
            # Determinar si entra como admin según la selección
            es_admin = bool(usuario["es_administrador"] and rol_seleccionado == "admin")
            
            # Limpiar sesión temporal
            session.pop("admin_validado", None)
            
            cur.close()

            # Guardar sesión
            session["usuario"] = {
                "correo": correo,
                "ci": ci,
                "es_administrador": es_admin,
                "es_invitado": False
            }

            return redirect(url_for("inicio"))

        # Buscar usuario normal
        cur.execute("""
            SELECT correo, contraseña, es_administrador 
            FROM login 
            WHERE correo = %s
        """, (correo,))
        usuario = cur.fetchone()

        # Buscar invitado
        cur.execute("""
            SELECT email, contraseña_temporal 
            FROM invitados 
            WHERE email = %s
        """, (correo,))
        invitado = cur.fetchone()

        # Ninguno coincide
        if not usuario and not invitado:
            cur.close()
            return render_template("login.html", error="El correo no está registrado.")

        # Validación de contraseña
        if usuario:  
            # Usuario normal → contraseña hasheada
            if not check_password_hash(usuario["contraseña"], contraseña):
                cur.close()
                return render_template("login.html", error="Contraseña incorrecta.")

            # Si es administrador y no ha seleccionado rol, mostrar opciones
            if usuario["es_administrador"]:
                # Guardar en sesión temporal que ya validamos este correo
                session["admin_validado"] = correo
                cur.close()
                return render_template("login.html", 
                                       mostrar_seleccion_admin=True, 
                                       correo=correo)

            # Buscar CI del participante (usuarios no admin)
            cur.execute("SELECT ci FROM participante WHERE email = %s", (correo,))
            participante = cur.fetchone()
            ci = participante["ci"] if participante else None
            es_admin = False
            es_inv = False

        else:  
            # Invitado → contraseña temporal en texto plano
            if not check_password_hash(invitado["contraseña_temporal"], contraseña):
                cur.close()
                return render_template("login.html", error="Contraseña incorrecta.")

            # Comprobar si puede ingresar hoy
            cur.execute("SELECT fecha_ingreso FROM invitados WHERE email = %s", (correo,))
            fecha_row = cur.fetchone()

            if not fecha_row:
                cur.close()
                return render_template("login.html", error="Error interno.")

            fecha_ingreso = fecha_row["fecha_ingreso"]

            from datetime import date
            if fecha_ingreso != date.today():
                cur.close()
                return render_template("login.html", error="Usted no puede ingresar hoy.")

            # Buscar CI del invitado
            cur.execute("SELECT ci_invitado FROM invitados WHERE email = %s", (correo,))
            participante = cur.fetchone()
            ci = participante["ci_invitado"] if participante else None
            es_admin = False
            es_inv = True

        cur.close()

        # Guardar sesión
        session["usuario"] = {
            "correo": correo,
            "ci": ci,
            "es_administrador": es_admin,
            "es_invitado": bool(es_inv)
        }

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

    return render_template("inicio.html")


# ---------------------------
# Salas
# ---------------------------
@app.get("/salas")
def salas_listado():
    need = _require_login()
    if need: 
        return need

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    edificio = request.args.get("edificio")
    tipo_sala = request.args.get("tipo_sala")
    cap_min = request.args.get("cap_min", type=int)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = [r["nombre_edificio"] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT tipo_sala FROM sala ORDER BY tipo_sala")
    tipos = [r["tipo_sala"] for r in cur.fetchall()]

    sql = "SELECT nombre_sala, edificio, capacidad, tipo_sala FROM sala"
    filtros = []
    params = []

    if edificio:
        filtros.append("edificio = %s")
        params.append(edificio)

    if tipo_sala:
        filtros.append("tipo_sala = %s")
        params.append(tipo_sala)

    if cap_min:
        filtros.append("capacidad >= %s")
        params.append(cap_min)

    # Si hay filtros, se agregan al SQL
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)

    sql += " ORDER BY edificio, nombre_sala"

    # Ejecutamos
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

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    edificio = request.args.get("edificio")
    nombre_sala = request.args.get("nombre_sala")
    fecha = request.args.get("fecha")

    if not edificio or not nombre_sala:
        flash("Faltan parámetros de sala.", "danger")
        return redirect(url_for("salas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""SELECT nombre_sala, edificio, capacidad, tipo_sala
                   FROM sala
                   WHERE edificio = %s
                     AND nombre_sala = %s""",
                (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash("Sala no encontrada.", "danger")
        return redirect(url_for("salas_listado"))

    sala["img"] = _imagen_sala_url(sala["nombre_sala"])

    cur.execute("""
        SELECT id_turno,
            TIME_FORMAT(hora_inicio, '%%H:%%i') AS hora_inicio,
            TIME_FORMAT(hora_fin, '%%H:%%i') AS hora_fin
        FROM turno
        ORDER BY hora_inicio
    """)
    horarios = cur.fetchall()

    ocupados = []
    if fecha:
        cur.execute("""
                    SELECT TIME_FORMAT(t.hora_inicio, '%H:%i') hi
                    FROM reserva r
                             JOIN turno t ON t.id_turno = r.id_turno
                    WHERE r.edificio = %s
                      AND r.nombre_sala = %s
                      AND r.fecha = %s
                      AND r.estado IN ('activa', 'sin asistencia', 'finalizada')
                    """, (edificio, nombre_sala, fecha))
        ocupados = [row["hi"] for row in cur.fetchall()]
    cur.close()

    return render_template("sala.html", sala=sala, horarios=horarios, ocupados=ocupados)


@app.get("/salas/<path:edificio>/<path:nombre_sala>")
def sala_detalle(edificio, nombre_sala):
    need = _require_login()
    if need:
        return need

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    fecha = request.args.get("fecha")  
    if not fecha:
        fecha = date.today().isoformat()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
                SELECT nombre_sala, edificio, capacidad, tipo_sala
                FROM sala
                WHERE edificio = %s
                  AND nombre_sala = %s
                """, (edificio, nombre_sala))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash("Sala no encontrada.", "danger")
        return redirect(url_for("salas_listado"))

    # --- Obtener imagen de la sala ---
    img = _imagen_sala_url(sala["nombre_sala"])

    # Turnos del día
    cur.execute("""
        SELECT 
            id_turno,
            TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
            TIME_FORMAT(hora_fin, '%H:%i') AS hora_fin
        FROM turno
        ORDER BY hora_inicio
    """)
    horarios = cur.fetchall()

    # Marcamos ocupados si pasaron fecha
    ocupados = []
    if fecha:
        cur.execute("""
                    SELECT TIME_FORMAT(t.hora_inicio, '%%H:%%i') AS hi
                    FROM reserva r
                             JOIN turno t ON t.id_turno = r.id_turno
                    WHERE r.edificio = %s
                      AND r.nombre_sala = %s
                      AND r.fecha = %s
                      AND r.estado IN ('activa', 'sin asistencia', 'finalizada')
                    """, (edificio, nombre_sala, fecha))
        ocupados = [row["hi"] for row in cur.fetchall()]

    print("HORARIOS:", horarios)
    print("OCUPADOS:", ocupados)
    cur.close()
    return render_template("sala.html", sala=sala, horarios=horarios, ocupados=ocupados, img=img)


# ---------------------------------
# ABM Salas (solo administradores)
# ---------------------------------
@app.get('/salas/nueva')
def salas_nueva_form():
    need = _require_login()
    if need: return need

    if not session['usuario'].get('es_administrador'):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('salas_listado'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT nombre_edificio FROM edificio ORDER BY nombre_edificio')
    edificios = [r['nombre_edificio'] for r in cur.fetchall()]
    cur.close()
    return render_template('sala_form.html', edificios=edificios, sala=None, accion='Crear')


@app.post('/salas/nueva')
def salas_nueva():
    need = _require_login()
    if need: return need

    if not session['usuario'].get('es_administrador'):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('salas_listado'))

    nombre = request.form.get('nombre_sala')
    edificio = request.form.get('edificio')
    capacidad = request.form.get('capacidad', type=int)
    tipo = request.form.get('tipo_sala')

    if not nombre or not edificio or capacidad is None or capacidad < 0 or not tipo:
        flash('Complete todos los campos correctamente.', 'danger')
        return redirect(url_for('salas_nueva_form'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute('INSERT INTO sala (nombre_sala, edificio, capacidad, tipo_sala) VALUES (%s,%s,%s,%s)',
                    (nombre, edificio, capacidad, tipo))
        mysql.connection.commit()
        flash('Sala creada correctamente.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al crear sala: {e}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('salas_listado'))


@app.get('/salas/<path:edificio>/<path:nombre_sala>/editar')
def salas_editar_form(edificio, nombre_sala):
    need = _require_login()
    if need: return need

    if not session['usuario'].get('es_administrador'):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('salas_listado'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute('SELECT nombre_sala, edificio, capacidad, tipo_sala FROM sala WHERE nombre_sala=%s AND edificio=%s',
                (nombre_sala, edificio))
    sala = cur.fetchone()
    if not sala:
        cur.close()
        flash('Sala no encontrada.', 'danger')
        return redirect(url_for('salas_listado'))

    cur.execute('SELECT nombre_edificio FROM edificio ORDER BY nombre_edificio')
    edificios = [r['nombre_edificio'] for r in cur.fetchall()]
    cur.close()
    return render_template('sala_form.html', edificios=edificios, sala=sala, accion='Editar')


@app.post('/salas/<path:edificio>/<path:nombre_sala>/editar')
def salas_editar(edificio, nombre_sala):
    need = _require_login()
    if need: return need

    if not session['usuario'].get('es_administrador'):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('salas_listado'))

    nombre_new = request.form.get('nombre_sala')
    edificio_new = request.form.get('edificio')
    capacidad = request.form.get('capacidad', type=int)
    tipo = request.form.get('tipo_sala')

    if not nombre_new or not edificio_new or capacidad is None or capacidad < 0 or not tipo:
        flash('Complete todos los campos correctamente.', 'danger')
        return redirect(url_for('salas_editar_form', edificio=edificio, nombre_sala=nombre_sala))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute('''
            UPDATE sala
            SET nombre_sala=%s, edificio=%s, capacidad=%s, tipo_sala=%s
            WHERE nombre_sala=%s AND edificio=%s
        ''', (nombre_new, edificio_new, capacidad, tipo, nombre_sala, edificio))
        if cur.rowcount == 0:
            flash('No se actualizó ninguna fila (sala no encontrada).', 'warning')
        else:
            mysql.connection.commit()
            flash('Sala actualizada correctamente.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al actualizar sala: {e}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('salas_listado'))


@app.post('/salas/<path:edificio>/<path:nombre_sala>/eliminar')
def salas_eliminar(edificio, nombre_sala):
    need = _require_login()
    if need: return need

    if not session['usuario'].get('es_administrador'):
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('salas_listado'))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    # Verificar si existen reservas asociadas
    cur.execute('''SELECT 1 FROM reserva WHERE nombre_sala=%s AND edificio=%s LIMIT 1''', (nombre_sala, edificio,))
    if cur.fetchone():
        cur.close()
        flash('No se puede eliminar la sala porque tiene reservas asociadas.', 'danger')
        return redirect(url_for('salas_listado'))

    try:
        cur.execute('DELETE FROM sala WHERE nombre_sala=%s AND edificio=%s', (nombre_sala, edificio))
        if cur.rowcount == 0:
            flash('Sala no encontrada.', 'warning')
        else:
            mysql.connection.commit()
            flash('Sala eliminada.', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar sala: {e}', 'danger')
    finally:
        cur.close()

    return redirect(url_for('salas_listado'))


# ---------------------------
# Reservas (listado, detalle, crear, unirse)
# ---------------------------
@app.get("/reservas")
def reservas_listado():
    need = _require_login()
    if need:
        return need

    estado = request.args.get("estado")
    fecha = request.args.get("fecha")
    sala_like = request.args.get("sala")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    sql = """
          SELECT r.id_reserva,
                 r.fecha,
                 TIME_FORMAT(t.hora_inicio, '%%H:%%i') AS hora_inicio,
                 TIME_FORMAT(t.hora_fin, '%%H:%%i')    AS hora_fin,
                 r.nombre_sala,
                 r.edificio,
                 r.estado
          FROM reserva r
                   JOIN turno t ON t.id_turno = r.id_turno
          """
    params = []
    if estado:
        sql += " AND r.estado=%s"
        params.append(estado)
    if fecha:
        sql += " AND r.fecha=%s"
        params.append(fecha)
    if sala_like:
        sql += " AND r.nombre_sala LIKE %s"
        params.append(f"%{sala_like}%")
    sql += " ORDER BY r.fecha DESC, t.hora_inicio DESC"

    cur.execute(sql, tuple(params))
    reservas = cur.fetchall()

    # Hashear los IDs de las reservas
    for reserva in reservas:
        reserva['id_hash'] = hash_id(reserva['id_reserva'])
    cur.close()

    es_admin = session['usuario'].get('es_administrador', False)

    return render_template("reservas.html", reservas=reservas, es_admin=es_admin)

@app.get("/reservas/<string:hashed_id>")
def reserva_detalle(hashed_id):
    need = _require_login()
    if need:
        return need

    # Convertir hash a ID
    id_reserva = unhash_id(hashed_id)
    if id_reserva is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # --- Obtener información principal de la reserva ---
    cur.execute("""
                SELECT r.id_reserva,
                       r.fecha,
                       r.estado,
                       r.nombre_sala,
                       s.edificio,
                       s.capacidad,
                       s.tipo_sala,
                       e.direccion,
                       TIME_FORMAT(t.hora_inicio, '%%H:%%i') AS hora_inicio,
                       TIME_FORMAT(t.hora_fin, '%%H:%%i')    AS hora_fin
                FROM reserva r
                         JOIN sala s ON s.nombre_sala = r.nombre_sala AND s.edificio = r.edificio
                         JOIN edificio e on s.edificio = e.nombre_edificio
                         JOIN turno t ON t.id_turno = r.id_turno
                WHERE r.id_reserva = %s
                """, (id_reserva,))
    r = cur.fetchone()

    if not r:
        cur.close()
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    # Agregar hash al resultado
    r['id_hash'] = hashed_id

    # --- Participantes de la reserva ---
    cur.execute("""
                SELECT p.ci, CONCAT(p.nombre, ' ', p.apellido) AS nombre, rp.asistencia
                FROM reserva_participante rp
                         JOIN participante p ON p.ci = rp.ci_participante
                WHERE rp.id_reserva = %s
                ORDER BY p.apellido, p.nombre
                """, (id_reserva, ))
    participantes = cur.fetchall()

    # --- Verificar si el usuario actual forma parte de la reserva ---
    cur.execute("""
                SELECT 1
                FROM reserva_participante
                WHERE id_reserva = %s
                  AND ci_participante = %s
                """, (id_reserva, session["usuario"]["ci"]))
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

@app.post("/reservas/<string:hashed_id>/eliminar")
def reservas_eliminar(hashed_id):
    need = _require_login()
    if need: return need

    if not session["usuario"].get("es_administrador"):
        flash("No tienes permiso para eliminar reservas.", "danger")
        return redirect(url_for("reservas_listado"))

    # Convertir hash a ID
    id_reserva = unhash_id(hashed_id)
    if id_reserva is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Borramos participantes primero por FK
    cur.execute("DELETE FROM reserva_participante WHERE id_reserva=%s", (id_reserva, ))

    # Borramos la reserva
    cur.execute("DELETE FROM reserva WHERE id_reserva=%s", (id_reserva, ))
    mysql.connection.commit()
    cur.close()

    flash("Reserva eliminada correctamente.", "success")
    return redirect(url_for("reservas_listado"))

@app.route("/reservas/<string:hashed_id>/editar", methods=["GET","POST"])
def reservas_editar(hashed_id):
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        flash("No tienes permiso para modificar reservas.", "danger")
        return redirect(url_for("reservas_listado"))

    # Convertir hash a ID
    id_reserva = unhash_id(hashed_id)
    if id_reserva is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        edificio = request.form.get("edificio")
        nombre_sala = request.form.get("nombre_sala")
        fecha = request.form.get("fecha")
        id_turno = request.form.get("id_turno", type=int)
        nuevo_estado = request.form.get("estado")

        # Validaciones
        if not all([edificio, nombre_sala, fecha, id_turno, nuevo_estado]):
            flash("Todos los campos son obligatorios.", "danger")
            cur.close()
            return redirect(url_for("reservas_editar", hashed_id=hashed_id, ))

        # Validar que el estado sea válido
        estados_validos = ['activa', 'cancelada', 'finalizada', 'sin asistencia']
        if nuevo_estado not in estados_validos:
            flash("Estado no válido.", "danger")
            cur.close()
            return redirect(url_for("reservas_editar", hashed_id=hashed_id))

        # Verificar que la reserva existe
        cur.execute("SELECT * FROM reserva WHERE id_reserva=%s", (id_reserva,))
        reserva_actual = cur.fetchone()

        if not reserva_actual:
            flash("Reserva no encontrada.", "danger")
            cur.close()
            return redirect(url_for("reservas_listado"))

        # Verificar que la sala existe en el edificio
        cur.execute("""
            SELECT nombre_sala 
            FROM sala 
            WHERE nombre_sala=%s AND edificio=%s
        """, (nombre_sala, edificio))

        if not cur.fetchone():
            flash("La sala no existe en ese edificio.", "danger")
            cur.close()
            return redirect(url_for("reservas_editar", hashed_id=hashed_id))

        # Verificar que el turno existe
        cur.execute("SELECT id_turno FROM turno WHERE id_turno=%s", (id_turno,))
        if not cur.fetchone():
            flash("El turno seleccionado no existe.", "danger")
            cur.close()
            return redirect(url_for("reservas_editar", hashed_id=hashed_id))

        # Validar fecha (no permitir fechas pasadas)
        fecha_obj = datetime.strptime(fecha, "%Y-%m-%d").date()
        if fecha_obj < date.today():
            flash("No se puede asignar una fecha pasada.", "danger")
            cur.close()
            return redirect(url_for("reservas_editar", hashed_id=hashed_id))

        # Verificar si el turno está ocupado (solo si cambió sala/fecha/turno)
        cambio_horario = (
            edificio != reserva_actual["edificio"] or
            nombre_sala != reserva_actual["nombre_sala"] or
            fecha != str(reserva_actual["fecha"]) or
            id_turno != reserva_actual["id_turno"]
        )

        if cambio_horario:
            cur.execute("""
                SELECT id_reserva 
                FROM reserva 
                WHERE edificio=%s 
                  AND nombre_sala=%s 
                  AND fecha=%s 
                  AND id_turno=%s 
                  AND id_reserva != %s
                  AND estado IN ('activa', 'sin asistencia', 'finalizada')
            """, (edificio, nombre_sala, fecha, id_turno, id_reserva))

            if cur.fetchone():
                flash("Ese horario ya está ocupado por otra reserva.", "danger")
                cur.close()
                return redirect(url_for("reservas_editar", hashed_id=hashed_id))

        # Actualizar la reserva
        cur.execute("""
            UPDATE reserva
            SET edificio=%s,
                nombre_sala=%s,
                fecha=%s,
                id_turno=%s,
                estado=%s
            WHERE id_reserva=%s
        """, (edificio, nombre_sala, fecha, id_turno, nuevo_estado, id_reserva))

        mysql.connection.commit()
        cur.close()

        flash("Reserva modificada correctamente.", "success")
        return redirect(url_for("reserva_detalle", hashed_id=hashed_id))

    # GET obtener datos actuales
    cur.execute("SELECT * FROM reserva WHERE id_reserva=%s", (id_reserva,))
    r = cur.fetchone()

    if not r:
        flash("Reserva no encontrada.", "danger")
        cur.close()
        return redirect(url_for("reservas_listado"))

    # Agregar hash
    r['id_hash'] = hashed_id

    # Obtener edificios
    cur.execute("SELECT DISTINCT nombre_edificio FROM edificio ORDER BY nombre_edificio")
    edificios = cur.fetchall()

    # Obtener todas las salas agrupadas por edificio (para JavaScript)
    cur.execute("""
        SELECT edificio, nombre_sala 
        FROM sala 
        ORDER BY edificio, nombre_sala
    """)
    todas_salas = cur.fetchall()

    # Crear diccionario de salas por edificio
    salas_por_edificio = {}
    for s in todas_salas:
        if s["edificio"] not in salas_por_edificio:
            salas_por_edificio[s["edificio"]] = []
        salas_por_edificio[s["edificio"]].append(s["nombre_sala"])

    # Obtener turnos
    cur.execute("""
        SELECT id_turno, 
               TIME_FORMAT(hora_inicio, '%H:%i') AS hora_inicio,
               TIME_FORMAT(hora_fin, '%H:%i') AS hora_fin
        FROM turno
        ORDER BY hora_inicio
    """)
    turnos = cur.fetchall()

    # Obtener participantes de la reserva
    cur.execute("""
        SELECT p.ci, CONCAT(p.nombre, ' ', p.apellido) AS nombre
        FROM reserva_participante rp
        JOIN participante p ON p.ci = rp.ci_participante
        WHERE rp.id_reserva = %s
        ORDER BY p.apellido, p.nombre
    """, (id_reserva,))
    participantes = cur.fetchall()

    cur.close()

    import json
    salas_json = json.dumps(salas_por_edificio)

    return render_template("reserva_editar.html",
                         r=r,
                         edificios=edificios,
                         turnos=turnos,
                         participantes=participantes,
                         salas_json=salas_json)


# Nueva ruta para eliminar participante de una reserva
@app.route("/reservas/<string:hashed_id>/participante/<int:ci>/eliminar", methods=["POST"])
def reservas_eliminar_participante(hashed_id, ci):
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        flash("No tienes permiso para modificar reservas.", "danger")
        return redirect(url_for("reservas_listado"))

    # Convertir hash a ID
    id = unhash_id(hashed_id)
    if id is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Verificar que la reserva existe
    cur.execute("SELECT * FROM reserva WHERE id_reserva=%s", (id,))
    reserva = cur.fetchone()

    if not reserva:
        flash("Reserva no encontrada.", "danger")
        cur.close()
        return redirect(url_for("reservas_listado"))

    # Contar participantes actuales
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM reserva_participante
        WHERE id_reserva = %s
    """, (id,))
    total = cur.fetchone()["total"]

    # Eliminar al participante
    cur.execute("""
        DELETE FROM reserva_participante
        WHERE id_reserva = %s AND ci_participante = %s
    """, (id, ci))

    # Si era el último participante, cancelar la reserva
    if total == 1:
        cur.execute("""
            UPDATE reserva
            SET estado = 'cancelada'
            WHERE id_reserva = %s
        """, (id,))
        flash("Participante eliminado. La reserva se canceló por no tener participantes.", "warning")
    else:
        flash("Participante eliminado de la reserva.", "success")

    mysql.connection.commit()
    cur.close()

    return redirect(url_for("reservas_editar", hashed_id=hashed_id))

@app.route("/baja_reserva/<string:hashed_id>", methods=["POST"])
def baja_reserva(hashed_id):
    # Convertir hash a ID
    id_reserva = unhash_id(hashed_id)
    if id_reserva is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))

    user_ci = session["usuario"].get("ci")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Ver cuántos participantes hay en la reserva
    cur.execute("""
                SELECT COUNT(*) AS total
                FROM reserva_participante
                WHERE id_reserva = %s
                """, (id_reserva,))
    total = cur.fetchone()["total"]

    # Eliminar al usuario actual de la reserva
    cur.execute("""
                DELETE
                FROM reserva_participante
                WHERE id_reserva = %s
                  AND ci_participante = %s
                """, (id_reserva, user_ci))

    # Si era el único participante → cancelar la reserva
    if total == 1:
        cur.execute("""
                    UPDATE reserva
                    SET estado = 'cancelada'
                    WHERE id_reserva = %s
                    """, (id_reserva,))

    mysql.connection.commit()
    cur.close()

    flash("Te has dado de baja de la reserva.", "success")
    return redirect(url_for("reservas_listado", hashed_id=hashed_id))


@app.route("/reservas/nueva", methods=["GET", "POST"])
def reservas_crear():
    need = _require_login()
    if need:
        return need

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        edificio = request.form.get("edificio")
        nombre_sala = request.form.get("nombre_sala")
        fecha = request.form.get("fecha")
        id_turno = request.form.get("id_turno", type=int)
        clave_reserva = request.form.get("clave_reserva")

        if not (edificio and nombre_sala and fecha and id_turno and clave_reserva):
            flash("Faltan datos para crear la reserva (incluida la contraseña).", "danger")
            return redirect(url_for("reservas_crear", edificio=edificio, nombre_sala=nombre_sala, fecha=fecha))

        # <-- LLAMADA AL VERIFICADOR: manejar su respuesta correctamente
        reserva_validada = verificador(edificio, nombre_sala, fecha, id_turno)
        if reserva_validada is not True:
            # verificador devolvió un redirect/Response; devolverlo inmediatamente
            return reserva_validada
        
        #hasheamos la contraseña de la reserva
        if not clave_reserva.startswith("scrypt:32768:8:1$"):
            clave_hasheada = generate_password_hash(clave_reserva)

        #si verificador devolvió True => crear reserva
        cur.execute("""
                    INSERT INTO reserva (nombre_sala, edificio, fecha, id_turno, estado, clave_reserva)
                    VALUES (%s, %s, %s, %s, 'activa', %s)
                    """, (nombre_sala, edificio, fecha, id_turno, clave_hasheada))

        cur.execute(""" 
                    SELECT id_reserva 
                    FROM reserva 
                    WHERE nombre_sala = %s AND edificio = %s AND fecha = %s AND id_turno=%s AND clave_reserva = %s
                    """, (nombre_sala, edificio,  fecha, id_turno, clave_hasheada))
        id_reserva = cur.fetchone()["id_reserva"]


        # Auto-agregar usuario logueado si existe en participante
        ci = session["usuario"]["ci"]
        if ci:
            cur.execute("""
                INSERT IGNORE INTO reserva_participante 
                    (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
                VALUES (%s, %s, %s, false)
            """, (ci, id_reserva, date.today()))

        mysql.connection.commit()
        cur.close()

        hashed_id = hash_id(id_reserva)

        flash("Reserva creada.", "success")
        return redirect(url_for("reserva_detalle", hashed_id=hashed_id))

    # -- GET --
    edificio = request.args.get("edificio")
    nombre_sala = request.args.get("nombre_sala")
    fecha = request.args.get("fecha")

    if not (edificio and nombre_sala):
        flash("Faltan parámetros de sala.", "danger")
        return redirect(url_for("salas_listado"))

    cur.execute("""
                SELECT nombre_sala, edificio, capacidad, tipo_sala
                FROM sala
                WHERE edificio = %s
                  AND nombre_sala = %s
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
                           DATE_FORMAT(hora_inicio, '%H:%i') AS hi,
                           DATE_FORMAT(hora_fin, '%H:%i')    AS hf
                    FROM turno
                    ORDER BY hora_inicio
                    """)
        todos = cur.fetchall()

        cur.execute("""
                    SELECT id_turno
                    FROM reserva
                    WHERE edificio = %s
                      AND nombre_sala = %s
                      AND fecha = %s
                      AND estado IN ('activa', 'sin asistencia', 'finalizada')
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

    hashed_id = request.form.get("hashed_id")
    clave_ingresa = request.form.get("clave_reserva")

    if not hashed_id:
        flash("Reserva inválida.", "danger")
        return redirect(url_for("reservas_listado"))

    # Convertir hash a ID
    id_reserva = unhash_id(hashed_id)
    if id_reserva is None:
        flash("Reserva no encontrada.", "danger")
        return redirect(url_for("reservas_listado"))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Obtener CI del usuario logueado
    ci = session["usuario"]["ci"]
    if ci is None:
        flash("Tu correo no tiene CI asociado en participante.", "danger")
        return redirect(url_for("reservas_listado"))

    # Para obtener los datos de la reserva a la que se quiere unir:
    cur.execute("""
                SELECT r.edificio, r.nombre_sala, r.fecha, r.id_turno
                FROM reserva r
                WHERE r.id_reserva = %s
                """, (id_reserva,))
    datos = cur.fetchone()

    if not datos:
        cur.close()
        flash("La reserva no existe.", "danger")
        return redirect(url_for("reservas_listado"))

    # Llamada real al verificador
    verifica_validez = verificador(
        edificio=datos["edificio"],
        nombre_sala=datos["nombre_sala"],
        fecha=datos["fecha"],
        id_turno=datos["id_turno"],
        id_reserva=id_reserva,  # para que no cuente esta reserva como nueva
        clave_ingresa=clave_ingresa
    )

    if verifica_validez is not True:
        return verifica_validez
    else:
        cur.execute("""
                    INSERT INTO reserva_participante (ci_participante, id_reserva, fecha_solicitud_reserva, asistencia)
                    VALUES (%s, %s, %s, false)
                    """, (ci, id_reserva, date.today()))
        mysql.connection.commit()
        cur.close()

        flash("Te uniste a la reserva.", "success")
        return redirect(url_for("reserva_detalle", hashed_id=hashed_id))


# ---------------------------
# Asistencia (hoy)
# ---------------------------
@app.route("/asistencia", methods=["GET"])
def asistencia_index():
    need = _require_login()
    if need:
        return need

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Traer reservas de hoy con fecha y horas formateadas como strings
    cur.execute("""
        SELECT 
            r.id_reserva AS id,
            r.nombre_sala AS sala,
            DATE_FORMAT(r.fecha, '%d/%m/%Y') AS fecha,
            TIME_FORMAT(t.hora_inicio, '%H:%i') AS hora_inicio,
            TIME_FORMAT(t.hora_fin, '%H:%i') AS hora_fin
        FROM reserva r
        JOIN turno t ON t.id_turno = r.id_turno
        WHERE r.fecha = CURDATE()
        ORDER BY t.hora_inicio
    """)
    reservas_hoy = cur.fetchall()

    # Traer participantes por reserva
    for r in reservas_hoy:
        cur.execute("""
            SELECT p.ci,
                   p.nombre,
                   p.apellido,
                   IFNULL(rp.asistencia, 0) AS asistio
            FROM reserva_participante rp
            JOIN participante p ON p.ci = rp.ci_participante
            WHERE rp.id_reserva = %s
        """, (r["id"],))
        r["participantes"] = cur.fetchall()

    # DEBUG rápido: imprime en logs lo que se envía al template
    app.logger.debug("reservas_hoy: %s", reservas_hoy)

    cur.close()
    return render_template("asistencia.html", reservas_hoy=reservas_hoy)


@app.post("/asistencia/marcar")
def asistencia_marcar():
    need = _require_login()
    if need: 
        return need
    
    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))

    id_reserva = request.form.get("id_reserva", type=int)
    if not id_reserva:
        flash("Reserva inválida.", "danger")
        return redirect(url_for("asistencia_index"))

    # Obtener lista de CI marcados como asistieron
    asistentes = request.form.getlist("asistio")  # ej ["123", "555"]

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Validar fecha del día
    cur.execute("SELECT fecha FROM reserva WHERE id_reserva=%s", (id_reserva,))
    row = cur.fetchone()

    if not row or str(row["fecha"]) != str(date.today()):
        cur.close()
        flash("La asistencia solo se puede marcar el mismo día de la reserva.", "warning")
        return redirect(url_for("asistencia_index"))

    # 1) Poner asistencia = 1 a los marcados
    if asistentes:
        cur.execute("""
            UPDATE reserva_participante
            SET asistencia = 1
            WHERE id_reserva = %s AND ci_participante IN ({})
        """.format(",".join(["%s"] * len(asistentes))),
        [id_reserva] + asistentes)

    # 2) Poner asistencia = 0 a los NO marcados
    cur.execute("""
        UPDATE reserva_participante
        SET asistencia = 0
        WHERE id_reserva = %s
          AND ci_participante NOT IN ({})
    """.format(",".join(["%s"] * len(asistentes))) if asistentes else
    """
        UPDATE reserva_participante
        SET asistencia = 0
        WHERE id_reserva = %s
    """,
    [id_reserva] + asistentes if asistentes else [id_reserva])

    # 3) Si nadie asistió → actualizar reserva a "sin asistencia"
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM reserva_participante
        WHERE id_reserva=%s AND asistencia=1
    """, (id_reserva,))
    total_asistieron = cur.fetchone()["total"]

    if total_asistieron == 0:
        cur.execute("""
            UPDATE reserva
            SET estado = 'sin asistencia'
            WHERE id_reserva = %s
        """, (id_reserva,))

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

    usuario = session["usuario"]
    ci_usuario = usuario["ci"]        
    es_admin = usuario.get("es_administrador", False)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if es_admin:
        # Admin ve todo
        cur.execute("""
            SELECT p.ci,
                   CONCAT(p.nombre, ' ', p.apellido) nombre,
                   s.fecha_inicio desde,
                   s.fecha_fin hasta
            FROM sancion_participante s
            JOIN participante p ON p.ci = s.ci_participante
            ORDER BY s.fecha_inicio DESC
        """)
    else:
        # Usuario común solo ve sus sanciones
        cur.execute("""
            SELECT p.ci,
                   CONCAT(p.nombre, ' ', p.apellido) nombre,
                   s.fecha_inicio desde,
                   s.fecha_fin hasta
            FROM sancion_participante s
            JOIN participante p ON p.ci = s.ci_participante
            WHERE p.ci = %s
            ORDER BY s.fecha_inicio DESC
        """, (ci_usuario,))

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

    return render_template("sanciones.html", sanciones=sanciones, es_admin=es_admin)

@app.route("/sanciones/editar/<int:ci>", methods=["GET", "POST"])
def sanciones_editar(ci):
    need = _require_login()
    if need: 
        return need

    # Solo admins
    if not session["usuario"].get("es_administrador"):
        flash("No tienes permiso para modificar sanciones.", "danger")
        return redirect(url_for("sanciones_listado"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        # Recibimos fechas como 'YYYY-MM-DD' desde el form
        nueva_desde = request.form.get("fecha_inicio")
        nuevo_hasta = request.form.get("fecha_fin")

        if not (nueva_desde and nuevo_hasta):
            flash("Faltan fechas.", "danger")
            cur.close()
            return redirect(url_for("sanciones_editar", ci=ci))

        cur.execute("""
            UPDATE sancion_participante
            SET fecha_inicio = %s,
                fecha_fin = %s
            WHERE ci_participante = %s
        """, (nueva_desde, nuevo_hasta, ci))

        mysql.connection.commit()
        cur.close()
        flash("Sanción actualizada correctamente.", "success")
        return redirect(url_for("sanciones_listado"))

    # -- GET: traer la sanción actual --
    cur.execute("""
        SELECT ci_participante AS ci, fecha_inicio, fecha_fin
        FROM sancion_participante
        WHERE ci_participante = %s
        LIMIT 1
    """, (ci,))
    fila = cur.fetchone()
    cur.close()

    if not fila:
        flash("Sanción no encontrada.", "danger")
        return redirect(url_for("sanciones_listado"))

    # Pasamos la fila a la plantilla
    return render_template("sancion_editar.html", s=fila)

@app.post("/sanciones/eliminar/<int:ci>")
def sanciones_eliminar(ci):
    need = _require_login()
    if need: return need

    if not session["usuario"].get("es_administrador"):
        flash("No tienes permiso para eliminar sanciones.", "danger")
        return redirect(url_for("sanciones_listado"))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM sancion_participante WHERE ci_participante = %s", (ci,))
    mysql.connection.commit()
    cur.close()

    flash("Sanción eliminada.", "success")
    return redirect(url_for("sanciones_listado"))


# ---------------------------
# Reportes
# ---------------------------
@app.get("/reportes")
def reportes_index():
    need = _require_login()
    if need:
        return need

    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))

    # Tipo de reporte seleccionado
    tipo = request.args.get("tipo_reporte", "uso_salas")
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    # Inicializar variables
    salas = []
    turnos = []
    prom = []
    reservas = []
    ocupacion = []
    usadas = []
    sanciones = []
    edificios = []
    carreras = []
    reservas_asistencias = []
    sanciones_rol = []
    reservas_turno = []
    reservas_semestre = []

    # ====================================================================
    # 1) SALAS MÁS RESERVADAS
    # ====================================================================
    if tipo == 'uso_salas':
        # Obtener lista de edificios para el filtro
        cur.execute("SELECT DISTINCT edificio FROM sala ORDER BY edificio")
        edificios = cur.fetchall()
        
        # Filtro por edificio (opcional)
        edificio_filtro = request.args.get('edificio', '')
        
        if edificio_filtro:
            # Consulta adaptada con filtro de edificio
            cur.execute("""
                SELECT r.nombre_sala, s.edificio, COUNT(*) as total
                FROM reserva r
                JOIN sala s ON r.nombre_sala = s.nombre_sala
                WHERE s.edificio = %s
                GROUP BY r.nombre_sala, s.edificio
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM reserva r2
                        JOIN sala s2 ON r2.nombre_sala = s2.nombre_sala
                        WHERE s2.edificio = %s
                        GROUP BY r2.nombre_sala
                    ) sub
                )
            """, (edificio_filtro, edificio_filtro))
        else:
            cur.execute("""
                SELECT r.nombre_sala, r.edificio, COUNT(*) as total
                FROM reserva r
                GROUP BY r.nombre_sala, r.edificio
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM reserva
                        GROUP BY nombre_sala
                    ) sub
                )
            """)
        
        salas = cur.fetchall()

    # ====================================================================
    # 2) TURNOS MÁS DEMANDADOS
    # ====================================================================
    elif tipo == 'turnos_mas':
        rango = request.args.get('rango', '')
        
        if rango == 'mañana':
            # Turnos más demandados en la mañana
            cur.execute("""
                SELECT t.hora_inicio, t.hora_fin, COUNT(*) as total
                FROM turno t
                JOIN reserva r ON t.id_turno = r.id_turno
                WHERE t.hora_inicio >= '06:00:00' AND t.hora_inicio < '12:00:00'
                GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM turno t2
                        JOIN reserva r2 ON t2.id_turno = r2.id_turno
                        WHERE t2.hora_inicio >= '06:00:00' AND t2.hora_inicio < '12:00:00'
                        GROUP BY t2.id_turno
                    ) sub
                )
            """)
        elif rango == 'tarde':
            # Turnos más demandados en la tarde
            cur.execute("""
                SELECT t.hora_inicio, t.hora_fin, COUNT(*) as total
                FROM turno t
                JOIN reserva r ON t.id_turno = r.id_turno
                WHERE t.hora_inicio >= '12:00:00' AND t.hora_inicio < '18:00:00'
                GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM turno t2
                        JOIN reserva r2 ON t2.id_turno = r2.id_turno
                        WHERE t2.hora_inicio >= '12:00:00' AND t2.hora_inicio < '18:00:00'
                        GROUP BY t2.id_turno
                    ) sub
                )
            """)
        elif rango == 'noche':
            # Turnos más demandados en la noche
            cur.execute("""
                SELECT t.hora_inicio, t.hora_fin, COUNT(*) as total
                FROM turno t
                JOIN reserva r ON t.id_turno = r.id_turno
                WHERE t.hora_inicio >= '18:00:00' OR t.hora_inicio < '06:00:00'
                GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM turno t2
                        JOIN reserva r2 ON t2.id_turno = r2.id_turno
                        WHERE t2.hora_inicio >= '18:00:00' OR t2.hora_inicio < '06:00:00'
                        GROUP BY t2.id_turno
                    ) sub
                )
            """)
        else:
            cur.execute("""
                SELECT t.hora_inicio, t.hora_fin, COUNT(*) as total
                FROM turno t
                JOIN reserva r ON t.id_turno = r.id_turno
                GROUP BY t.id_turno, t.hora_inicio, t.hora_fin
                HAVING COUNT(*) = (
                    SELECT MAX(CantReservas) 
                    FROM (
                        SELECT COUNT(*) as CantReservas
                        FROM reserva
                        GROUP BY id_turno
                    ) sub
                )
            """)
        
        turnos = cur.fetchall()

    # ====================================================================
    # 3) PROMEDIO DE PARTICIPANTES POR SALA
    # ====================================================================
    elif tipo == 'prom_participantes':
        min_val = request.args.get('min', '')
        max_val = request.args.get('max', '')
        
        query = """
            SELECT s.nombre_sala, AVG(sub.CantParticipantes) as promedio
            FROM (
                SELECT r.nombre_sala, COUNT(rp.ci_participante) AS CantParticipantes
                FROM reserva r
                JOIN reserva_participante rp ON r.id_reserva = rp.id_reserva
                GROUP BY r.id_reserva, r.nombre_sala
            ) sub
            JOIN sala s ON sub.nombre_sala = s.nombre_sala
            GROUP BY s.nombre_sala
        """
        
        # Añadir filtros si existen
        having_clauses = []
        if min_val:
            having_clauses.append(f"AVG(sub.CantParticipantes) >= {float(min_val)}")
        if max_val:
            having_clauses.append(f"AVG(sub.CantParticipantes) <= {float(max_val)}")
        
        if having_clauses:
            query += " HAVING " + " AND ".join(having_clauses)
        
        cur.execute(query)
        prom = cur.fetchall()

    # ====================================================================
    # 4) CANTIDAD DE RESERVAS POR CARRERA Y FACULTAD
    # ====================================================================
    elif tipo == 'reservas_carrera':
        # Obtener lista de carreras para el filtro
        cur.execute("""
            SELECT DISTINCT pa.nombre_programa as carrera
            FROM programa_academico pa
            ORDER BY pa.nombre_programa
        """)
        carreras = cur.fetchall()
        
        carrera_filtro = request.args.get('carrera', '')
        
        if carrera_filtro:
            # Filtrar por carrera específica
            cur.execute("""
                SELECT f.nombre as facultad, pa.nombre_programa as carrera, 
                       COUNT(r.id_reserva) as total
                FROM facultad f
                LEFT JOIN programa_academico pa ON pa.id_facultad = f.id_facultad
                LEFT JOIN participante_programa_academico ppa ON pa.nombre_programa = ppa.nombre_programa
                LEFT JOIN reserva_participante rp ON ppa.ci_participante = rp.ci_participante
                LEFT JOIN reserva r ON r.id_reserva = rp.id_reserva
                WHERE pa.nombre_programa = %s
                GROUP BY f.nombre, pa.nombre_programa
            """, (carrera_filtro,))
        else:
            cur.execute("""
                SELECT f.nombre as facultad, pa.nombre_programa as carrera, 
                       COUNT(r.id_reserva) as total
                FROM facultad f
                LEFT JOIN programa_academico pa ON pa.id_facultad = f.id_facultad
                LEFT JOIN participante_programa_academico ppa ON pa.nombre_programa = ppa.nombre_programa
                LEFT JOIN reserva_participante rp ON ppa.ci_participante = rp.ci_participante
                LEFT JOIN reserva r ON r.id_reserva = rp.id_reserva
                GROUP BY f.nombre, pa.nombre_programa
                ORDER BY facultad
            """)
        
        reservas = cur.fetchall()

    # ====================================================================
    # 5) PORCENTAJE DE OCUPACIÓN DE SALAS POR EDIFICIO
    # ====================================================================
    elif tipo == 'ocupacion_salas':
        cur.execute("""
            SELECT e.nombre_edificio as nombre_sala, 
                   COUNT(r.id_reserva) / SUM(s.capacidad) * 100.00 AS ocupacion
            FROM edificio e
            JOIN sala s ON e.nombre_edificio = s.edificio
            JOIN reserva r ON r.nombre_sala = s.nombre_sala
            GROUP BY e.nombre_edificio
            ORDER BY ocupacion DESC
        """)
        ocupacion = cur.fetchall()

    # ====================================================================
    # 6) CANTIDAD DE RESERVAS Y ASISTENCIAS POR ROL
    # ====================================================================
    elif tipo == 'reservas_asistencias':
        cur.execute("""
            SELECT DISTINCT ppa.rol,
                   COUNT(rp.id_reserva) as CantReservas, 
                   COUNT(IF(rp.asistencia = True, 1, NULL)) as CantAsistencias
            FROM participante_programa_academico ppa
            JOIN reserva_participante rp ON ppa.ci_participante = rp.ci_participante
            GROUP BY ppa.rol
        """)
        reservas_asistencias = cur.fetchall()

    # ====================================================================
    # 7) CANTIDAD DE SANCIONES POR ROL
    # ====================================================================
    elif tipo == 'sanciones_rol':
        cur.execute("""
            SELECT ppa.rol, COUNT(DISTINCT sp.ci_participante) as CantSanciones
            FROM participante_programa_academico ppa
            JOIN reserva_participante rp ON ppa.ci_participante = rp.ci_participante
            JOIN sancion_participante sp ON rp.ci_participante = sp.ci_participante
            GROUP BY ppa.rol
        """)
        sanciones_rol = cur.fetchall()

    # ====================================================================
    # 8) PORCENTAJE DE RESERVAS UTILIZADAS VS NO UTILIZADAS
    # ====================================================================
    elif tipo == 'reservas_usadas':
        cur.execute("""
            SELECT
                IF(estado IN ('activa', 'finalizada'), 'Utilizadas', 'No utilizadas') AS estado_actuales,
                COUNT(*) / (SELECT COUNT(*) FROM reserva) * 100 AS porcentaje
            FROM reserva
            GROUP BY estado_actuales
        """)
        usadas = cur.fetchall()

    # ====================================================================
    # 9) RESERVAS POR TURNO (TODAS)
    # ====================================================================
    elif tipo == 'reservas_turno':
        cur.execute("""
            SELECT t.hora_inicio, t.hora_fin, COUNT(r.id_reserva) as total
            FROM turno t
            LEFT JOIN reserva r ON t.id_turno = r.id_turno
            GROUP BY t.hora_inicio, t.hora_fin
            ORDER BY t.hora_inicio
        """)
        reservas_turno = cur.fetchall()

    # ====================================================================
    # 10) RESERVAS REALIZADAS EN UN SEMESTRE ESPECÍFICO
    # ====================================================================
    elif tipo == 'reservas_semestre':
        # Permitir filtrar por fechas personalizadas
        fecha_inicio = request.args.get('fecha_inicio', '2025-08-12')
        fecha_fin = request.args.get('fecha_fin', '2025-12-05')
        
        cur.execute("""
            SELECT *
            FROM reserva r
            WHERE r.fecha BETWEEN %s AND %s
        """, (fecha_inicio, fecha_fin))
        reservas_semestre = cur.fetchall()

    # ====================================================================
    # 11) PARTICIPANTES CON SANCIONES
    # ====================================================================
    elif tipo == 'sanciones':
        cur.execute("""
            SELECT p.nombre, p.apellido, p.ci, 
                   COUNT(*) as CantSanciones,
                   MIN(sp.fecha_inicio) as fecha_inicio, 
                   MAX(sp.fecha_fin) as fecha_fin
            FROM participante p
            JOIN sancion_participante sp ON sp.ci_participante = p.ci
            GROUP BY p.nombre, p.apellido, p.ci
            ORDER BY p.apellido, p.nombre
        """)
        result = cur.fetchall()
        # Formatear nombre completo
        sanciones = []
        for row in result:
            sanciones.append({
                'ci': row['ci'],
                'nombre': f"{row['nombre']} {row['apellido']}",
                'cant_sanciones': row['CantSanciones'],
                'fecha_inicio': row['fecha_inicio'],
                'fecha_fin': row['fecha_fin']
            })

    cur.close()

    return render_template(
        "reportes.html",
        tipo=tipo,
        salas=salas,
        turnos=turnos,
        prom=prom,
        reservas=reservas,
        ocupacion=ocupacion,
        usadas=usadas,
        sanciones=sanciones,
        edificios=edificios,
        carreras=carreras,
        reservas_asistencias=reservas_asistencias,
        sanciones_rol=sanciones_rol,
        reservas_turno=reservas_turno,
        reservas_semestre=reservas_semestre
    )

#=================================================
# ABM(Alta, baja y modificación) de participantes e invitados
#=================================================
@app.route('/participantes',methods=["GET"])
def participantes_listado():
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    # Obtener participantes regulares
    cur.execute("""
        SELECT 
            p.ci, 
            p.nombre, 
            p.apellido, 
            p.email,
            l.es_administrador,
            'participante' as tipo
        FROM participante p
        LEFT JOIN login l ON p.email = l.correo
        ORDER BY p.apellido, p.nombre
    """)
    participantes_regulares = cur.fetchall()
    
    # Obtener invitados
    cur.execute("""
        SELECT 
            i.ci_invitado as ci,
            i.nombre_invitado as nombre,
            i.apellido_invitado as apellido,
            i.email,
            i.responsable_ci,
            i.fecha_ingreso,
            'invitado' as tipo,
            CONCAT(p.nombre, ' ', p.apellido) as nombre_responsable
        FROM invitados i
        LEFT JOIN participante p ON i.responsable_ci = p.ci
        ORDER BY i.apellido_invitado, i.nombre_invitado
    """)
    invitados = cur.fetchall()
    
    cur.close()
    
    # Combinar ambas listas
    todos_participantes = participantes_regulares + invitados
    
    # Obtener lista de participantes para el select de responsables
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT ci, CONCAT(nombre, ' ', apellido) as nombre_completo
        FROM participante
        ORDER BY apellido, nombre
    """)
    responsables = cur.fetchall()
    cur.close()
    
    return render_template('participantes.html', 
                         participantes=todos_participantes,
                         responsables=responsables)

@app.route('/participantes/agregar', methods=['POST'])
def participantes_agregar():
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))

    ci = request.form.get('ci', '').strip()
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    correo = request.form.get('email', '').strip()
    contraseña = request.form.get('contraseña', '').strip()
    rol = request.form.get('rol', '').strip()
    
    # Validaciones básicas
    if not all([ci, nombre, apellido, correo, contraseña, rol]):
        flash('Todos los campos son obligatorios', 'danger')
        return redirect(url_for('participantes_listado'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        if rol == 'invitado':
            # AGREGAR INVITADO
            responsable_ci = request.form.get('responsable_ci', '').strip()
            fecha_ingreso = request.form.get('fecha_ingreso', '').strip()
            
            if not responsable_ci or not fecha_ingreso:
                flash('Responsable y fecha de ingreso son obligatorios para invitados', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Verificar que el responsable existe
            cur.execute("SELECT ci FROM participante WHERE ci = %s", (responsable_ci,))
            if not cur.fetchone():
                flash('El responsable seleccionado no existe', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Verificar que no exista el CI en invitados
            cur.execute("SELECT ci_invitado FROM invitados WHERE ci_invitado = %s", (ci,))
            if cur.fetchone():
                flash('Ya existe un invitado con esa CI', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Verificar que no exista el email en invitados
            cur.execute("SELECT email FROM invitados WHERE email = %s", (correo,))
            if cur.fetchone():
                flash('Ya existe un invitado con ese correo', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Hash de la contraseña temporal
            hash_contraseña = generate_password_hash(contraseña)
            
            # Insertar invitado
            cur.execute("""
                INSERT INTO invitados (ci_invitado, nombre_invitado, apellido_invitado, 
                                      email, contraseña_temporal, responsable_ci, fecha_ingreso)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (ci, nombre, apellido, correo, hash_contraseña, responsable_ci, fecha_ingreso))
            
            mysql.connection.commit()
            flash(f'Invitado {nombre} {apellido} agregado exitosamente', 'success')
            
        else:
            # AGREGAR PARTICIPANTE REGULAR (user o admin)
            es_admin = 1 if rol == 'admin' else 0
            
            # Verificar que no exista el CI en participantes
            cur.execute("SELECT ci FROM participante WHERE ci = %s", (ci,))
            if cur.fetchone():
                flash('Ya existe un participante con esa CI', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Verificar que no exista el correo en login
            cur.execute("SELECT correo FROM login WHERE correo = %s", (correo,))
            if cur.fetchone():
                flash('Ya existe un usuario con ese correo', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Hash de la contraseña
            hash_contraseña = generate_password_hash(contraseña)
            
            # Insertar en participante
            cur.execute("""
                INSERT INTO participante (ci, nombre, apellido, email)
                VALUES (%s, %s, %s, %s)
            """, (ci, nombre, apellido, correo))
            
            # Insertar en login
            cur.execute("""
                INSERT INTO login (correo, contraseña, es_administrador)
                VALUES (%s, %s, %s)
            """, (correo, hash_contraseña, es_admin))
            
            mysql.connection.commit()
            flash(f'Participante {nombre} {apellido} agregado exitosamente', 'success')
            
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al agregar: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('participantes_listado'))

@app.route('/participantes/modificar/<int:ci>', methods=['POST'])
def participantes_modificar(ci):
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))
    
    nombre = request.form.get('nombre', '').strip()
    apellido = request.form.get('apellido', '').strip()
    correo = request.form.get('correo', '').strip()
    contraseña = request.form.get('contraseña', '').strip()
    rol = request.form.get('rol', '').strip()
    tipo_actual = request.form.get('tipo_actual', '').strip()
    
    if not all([nombre, apellido, correo, rol]):
        flash('Nombre, apellido, correo y rol son obligatorios', 'danger')
        return redirect(url_for('participantes_listado'))
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        if tipo_actual == 'invitado':
            # MODIFICAR INVITADO
            responsable_ci = request.form.get('responsable_ci', '').strip()
            fecha_ingreso = request.form.get('fecha_ingreso', '').strip()
            
            if rol == 'invitado':
                # Sigue siendo invitado, actualizar en invitados
                if not responsable_ci or not fecha_ingreso:
                    flash('Responsable y fecha de ingreso son obligatorios', 'danger')
                    cur.close()
                    return redirect(url_for('participantes_listado'))
                
                # Verificar que el responsable existe
                cur.execute("SELECT ci FROM participante WHERE ci = %s", (responsable_ci,))
                if not cur.fetchone():
                    flash('El responsable seleccionado no existe', 'danger')
                    cur.close()
                    return redirect(url_for('participantes_listado'))
                
                # Actualizar invitado
                cur.execute("""
                    UPDATE invitados 
                    SET nombre_invitado = %s, apellido_invitado = %s, email = %s,
                        responsable_ci = %s, fecha_ingreso = %s
                    WHERE ci_invitado = %s
                """, (nombre, apellido, correo, responsable_ci, fecha_ingreso, ci))
                
                # Si hay contraseña nueva
                if contraseña:
                    hash_contraseña = generate_password_hash(contraseña)
                    cur.execute("""
                        UPDATE invitados 
                        SET contraseña_temporal = %s
                        WHERE ci_invitado = %s
                    """, (hash_contraseña, ci))
                
                mysql.connection.commit()
                flash(f'Invitado {nombre} {apellido} modificado exitosamente', 'success')
            else:
                flash('No se puede cambiar un invitado a participante regular', 'warning')
                
        else:
            # MODIFICAR PARTICIPANTE REGULAR
            if rol == 'invitado':
                flash('No se puede cambiar un participante regular a invitado', 'warning')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            es_admin = 1 if rol == 'admin' else 0
            
            # Obtener el correo anterior
            cur.execute("SELECT email FROM participante WHERE ci = %s", (ci,))
            participante = cur.fetchone()
            
            if not participante:
                flash('Participante no encontrado', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            correo_anterior = participante['email']
            
            # Actualizar participante
            cur.execute("""
                UPDATE participante 
                SET nombre = %s, apellido = %s, email = %s
                WHERE ci = %s
            """, (nombre, apellido, correo, ci))
            
            # Si cambió el correo
            if correo != correo_anterior:
                # Verificar que el nuevo correo no exista
                cur.execute("SELECT correo FROM login WHERE correo = %s AND correo != %s", 
                          (correo, correo_anterior))
                if cur.fetchone():
                    raise Exception('El nuevo correo ya está en uso')
                
                # Actualizar correo en login
                cur.execute("""
                    UPDATE login 
                    SET correo = %s, es_administrador = %s
                    WHERE correo = %s
                """, (correo, es_admin, correo_anterior))
            else:
                # Solo actualizar es_administrador
                cur.execute("""
                    UPDATE login 
                    SET es_administrador = %s
                    WHERE correo = %s
                """, (es_admin, correo))
            
            # Si hay contraseña nueva
            if contraseña:
                hash_contraseña = generate_password_hash(contraseña)
                cur.execute("""
                    UPDATE login 
                    SET contraseña = %s
                    WHERE correo = %s
                """, (hash_contraseña, correo))
            
            mysql.connection.commit()
            flash(f'Participante {nombre} {apellido} modificado exitosamente', 'success')
            
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al modificar: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('participantes_listado'))


@app.route('/participantes/eliminar/<int:ci>', methods=['POST'])
def participantes_eliminar(ci):
    need = _require_login()
    if need:
        return need

    if not session["usuario"].get("es_administrador"):
        return redirect(url_for("inicio"))
    
    tipo = request.form.get('tipo', '').strip()
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    
    try:
        if tipo == 'invitado':
            # ELIMINAR INVITADO
            cur.execute("""
                SELECT nombre_invitado, apellido_invitado 
                FROM invitados 
                WHERE ci_invitado = %s
            """, (ci,))
            invitado = cur.fetchone()
            
            if not invitado:
                flash('Invitado no encontrado', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            nombre_completo = f"{invitado['nombre_invitado']} {invitado['apellido_invitado']}"
            
            # Verificar si tiene reservas activas
            cur.execute("""
                SELECT COUNT(*) as total 
                FROM reserva_participante rp
                JOIN reserva r ON rp.id_reserva = r.id_reserva
                WHERE rp.ci_participante = %s AND r.fecha >= CURDATE()
            """, (ci,))
            result = cur.fetchone()
            
            if result['total'] > 0:
                flash(f'No se puede eliminar: {nombre_completo} tiene reservas activas', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Eliminar invitado
            cur.execute("DELETE FROM invitados WHERE ci_invitado = %s", (ci,))
            mysql.connection.commit()
            flash(f'Invitado {nombre_completo} ha sido dado de baja exitosamente', 'warning')
            
        else:
            # ELIMINAR PARTICIPANTE REGULAR
            cur.execute("SELECT nombre, apellido, email FROM participante WHERE ci = %s", (ci,))
            participante = cur.fetchone()
            
            if not participante:
                flash('Participante no encontrado', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            nombre_completo = f"{participante['nombre']} {participante['apellido']}"
            correo = participante['email']
            
            # Verificar si tiene reservas activas
            cur.execute("""
                SELECT COUNT(*) as total 
                FROM reserva_participante rp
                JOIN reserva r ON rp.id_reserva = r.id_reserva
                WHERE rp.ci_participante = %s AND r.fecha >= CURDATE()
            """, (ci,))
            result = cur.fetchone()
            
            if result['total'] > 0:
                flash(f'No se puede eliminar: {nombre_completo} tiene reservas activas', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Verificar si es responsable de algún invitado
            cur.execute("""
                SELECT COUNT(*) as total 
                FROM invitados 
                WHERE responsable_ci = %s
            """, (ci,))
            result = cur.fetchone()
            
            if result['total'] > 0:
                flash(f'No se puede eliminar: {nombre_completo} es responsable de invitados', 'danger')
                cur.close()
                return redirect(url_for('participantes_listado'))
            
            # Eliminar login
            cur.execute("DELETE FROM login WHERE correo = %s", (correo,))
            
            # Eliminar participante
            cur.execute("DELETE FROM participante WHERE ci = %s", (ci,))
            
            mysql.connection.commit()
            flash(f'{nombre_completo} ha sido dado de baja exitosamente', 'warning')
            
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error al eliminar: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('participantes_listado'))

# ==========================================
# Recuperar contraseña (el login lo linkea)
# ==========================================
@app.route('/recuperar-contrasena', methods=["GET", "POST"])
def recuperar_contraseña():
    if request.method == "POST":
        flash("Si el correo existe, te enviamos un enlace.", "success")
        return redirect(url_for("login"))
    return render_template("recuperar_contraseña.html")


# --- Compat: enlaces antiguos a cambiar_contraseña ---
@app.get("/seguridad/cambiar-contrasena", endpoint="cambiar_contraseña")
def cambiar_contraseña_legacy():
    if session["usuario"].get("es_invitado"):
        return redirect(url_for("inicio"))
    
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