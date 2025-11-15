# ============================================================
# app.py  |  ÉBANO — Fase 1: Login / Registro / Tienda
#          COP -> USD (API configurable via .env) - Cache 12h
# ============================================================
from datetime import datetime
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, UserMixin, current_user
)
from dotenv import load_dotenv
import os
import requests
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from bd_config import get_connection
import bcrypt

# -----------------------
# Cargar variables .env
# -----------------------
load_dotenv()

# ------------------------------------------------------------
# CONFIGURACIÓN FLASK
# ------------------------------------------------------------
app = Flask(__name__)
# SECRET: usa variable de entorno si existe, si no usa valor por defecto (cambiar en producción)
app.secret_key = os.getenv("SECRET_KEY", os.getenv("clave_segura_ebano", "clave_segura_ebano_default"))
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv("WTF_CSRF_SECRET_KEY", app.secret_key)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------------------------------------------------
# CACHE y CONFIGURACIÓN DE TASA (COP -> USD)
# ------------------------------------------------------------
# TTL por defecto 12 horas (en segundos)
EXCHANGE_TTL_SECONDS = int(os.getenv("EXCHANGE_TTL_SECONDS", 60 * 60 * 12))
EXCHANGE_API_URL = os.getenv("EXCHANGE_API_URL", "https://api.exchangerate.host/latest")
EXCHANGE_API_KEY = os.getenv("CURRENCY_API_KEY", os.getenv("EXCHANGE_API_KEY", None))
EXCHANGE_REQUEST_TIMEOUT = int(os.getenv("EXCHANGE_REQUEST_TIMEOUT", 8))

# Caché simple en memoria
_app_exchange_cache = {"timestamp": 0.0, "cop_to_usd": None, "usd_to_cop": None}

# -------------------------
# Helpers de precios y filtros
# -------------------------
def parse_price_db(value):
    """
    Normaliza valores provenientes de la BD a Decimal (COP).
    Soporta int, float, Decimal, o strings con formatos comunes.
    """
    if value is None:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value).strip()
    # Manejar formatos "42.000,00", "42.000", "42,000.00", "42000"
    try:
        # caso "42.000,00" -> reemplazar '.' miles y ',' decimal -> "42000.00"
        if "." in s and "," in s and s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            # caso "42.000" (separador de miles) -> eliminar puntos si after part length == 3
            if s.count(".") == 1 and s.count(",") == 0:
                after = s.split(".")[1]
                if len(after) == 3:
                    s = s.replace(".", "")
            # caso "42,000" -> eliminar coma si es separador de miles
            if s.count(",") == 1 and s.count(".") == 0:
                after = s.split(",")[1]
                if len(after) == 3:
                    s = s.replace(",", "")
                else:
                    # "42000,00" o "42000.00"
                    s = s.replace(",", ".")
    except Exception:
        pass
    # quitar cualquier caracter no-numérico salvo punto y signo negativo
    cleaned = "".join(ch for ch in s if ch.isdigit() or ch in ".-")
    if cleaned in ("", ".", "-"):
        return Decimal(0)
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        # fallback: extraer dígitos
        digits = "".join(ch for ch in cleaned if ch.isdigit())
        return Decimal(digits) if digits else Decimal(0)


def format_cop(value):
    """
    Formato COP para admin: 42000 -> "42.000"
    """
    try:
        d = parse_price_db(value)
    except Exception:
        d = Decimal(0)
    amount = int(d.quantize(Decimal('1')))
    s = f"{amount:,}".replace(",", ".")
    return s


def get_cop_to_usd_rate_no_fallback():
    """
    Obtiene la tasa COP -> USD desde la API configurada.
    NO devuelve fallback; si falla, lanza RuntimeError.
    Espera que la API devuelva JSON con 'rates' y 'USD' OR una estructura similar.
    Usa EXCHANGE_API_URL y (opcional) EXCHANGE_API_KEY.
    """
    now = time.time()
    # cache
    if _app_exchange_cache["cop_to_usd"] is not None and (now - _app_exchange_cache["timestamp"]) < EXCHANGE_TTL_SECONDS:
        return Decimal(str(_app_exchange_cache["cop_to_usd"])), Decimal(str(_app_exchange_cache["usd_to_cop"]))

    # Preparar request
    params = {"base": "COP", "symbols": "USD"}
    headers = {}
    # Si se definió una API KEY en .env, incluirla según convenio 'access_key' (muchos proveedores usan ese nombre).
    if EXCHANGE_API_KEY:
        # incluir como param access_key si no está ya
        params["access_key"] = EXCHANGE_API_KEY

    try:
        resp = requests.get(EXCHANGE_API_URL, params=params, timeout=EXCHANGE_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        # buscar la tasa en distintas estructuras
        rate = None
        # Estructura más común: { "rates": { "USD": 0.00027 }, ... }
        if isinstance(data, dict) and "rates" in data and "USD" in data["rates"]:
            rate = data["rates"]["USD"]
        # Algunas APIs retornan directamente "USD": value in root
        elif isinstance(data, dict) and "USD" in data:
            rate = data["USD"]
        # Si no encontramos, lanzar
        if rate is None:
            raise RuntimeError("Respuesta inválida de la API de tasas: campo 'USD' ausente.")
        # normalizar y guardar en cache
        cop_to_usd = Decimal(str(rate))
        if cop_to_usd == 0:
            raise RuntimeError("Tasa COP->USD inválida (cero).")
        usd_to_cop = (Decimal('1') / cop_to_usd).quantize(Decimal('0.0001'))
        _app_exchange_cache["timestamp"] = now
        _app_exchange_cache["cop_to_usd"] = float(cop_to_usd)
        _app_exchange_cache["usd_to_cop"] = float(usd_to_cop)
        print("🔁 Tasa COP->USD actualizada desde API:", cop_to_usd)
        return cop_to_usd, usd_to_cop
    except requests.RequestException as re:
        raise RuntimeError(f"Error HTTP al obtener tasa (requests): {re}") from re
    except ValueError as ve:
        raise RuntimeError(f"Error al parsear respuesta de la API: {ve}") from ve
    except Exception as e:
        raise RuntimeError(f"Error inesperado al obtener tasa: {e}") from e


def cop_to_usd_decimal(cop_value):
    """
    Convierte un valor en COP (Decimal/int/str) a Decimal USD con 2 decimales.
    Usa la tasa obtenida por get_cop_to_usd_rate_no_fallback.
    """
    cop_dec = parse_price_db(cop_value)
    cop_to_usd, _ = get_cop_to_usd_rate_no_fallback()
    usd = (cop_dec * cop_to_usd).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return usd


def format_usd(value):
    """
    Para mostrar en plantillas: recibe valor en COP (o Decimal) y devuelve "$10.95 USD"
    Si hay error al obtener tasa, lanza y el caller deberá manejarlo o la plantilla mostrará fallback.
    """
    try:
        usd = cop_to_usd_decimal(value)
        formatted = "${:,.2f} USD".format(float(usd))
        return formatted
    except Exception as e:
        # No usar fallback silencioso: imprimimos error y devolvemos mensaje claro
        print("⚠️ format_usd error:", e)
        return "Tarifa USD no disponible"
    # Registrar filtros Jinja
app.jinja_env.filters['cop'] = format_cop
app.jinja_env.filters['usd'] = format_usd

# --- Ruta de prueba para obtener la tasa (usa la función que NO usa fallback) ---
@app.route("/api/rate")
def api_rate():
    """
    Devuelve JSON con la tasa actual COP->USD y USD->COP.
    Si la API externa falla, responde 502 con mensaje claro y no devuelbe fallback.
    """
    try:
        cop_to_usd_dec, usd_to_cop_dec = get_cop_to_usd_rate_no_fallback()
        return jsonify({
            "cop_to_usd": float(cop_to_usd_dec),
            "usd_to_cop": float(usd_to_cop_dec),
            "cached_at": _app_exchange_cache["timestamp"]
        })
    except RuntimeError as err:
        msg = str(err)
        print("❌ fetch_usd_cop_rate() error:", msg)
        return make_response(jsonify({"error": "No se pudo obtener la tasa USD/COP", "detail": msg}), 502)


# ------------------------------------------------------------
# MODELO DE USUARIO PARA FLASK-LOGIN
# ------------------------------------------------------------
class Usuario(UserMixin):
    def __init__(self, id, nombre_usuario, correo, rol):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.correo = correo
        self.rol = rol

# Cargar usuario por id (flask-login)
@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    if not conn:
        return None
    try:
        q = "SELECT id, nombre_usuario, correo, rol, nombre_completo FROM usuarios WHERE id = :id;"
        res = conn.run(q, id=user_id)
        if res:
            u = res[0]
            user = Usuario(u[0], u[1], u[2], u[3])
            try:
                user.nombre_completo = u[4] or u[1]
            except Exception:
                user.nombre_completo = u[1]
            return user
    except Exception as e:
        print("Error load_user:", e)
    finally:
        try: conn.close()
        except: pass
    return None

# ------------------------------------------------------------
# WTForms (Login / Registro / Reseña)
# ------------------------------------------------------------
class LoginForm(FlaskForm):
    correo = StringField("Correo electrónico", validators=[DataRequired(), Email()])
    contraseña = PasswordField("Contraseña", validators=[DataRequired()])
    submit = SubmitField("Iniciar sesión")

class RegistroForm(FlaskForm):
    nombre_completo = StringField("Nombre completo", validators=[DataRequired(), Length(min=3, max=150)])
    correo = StringField("Correo electrónico", validators=[DataRequired(), Email()])
    contraseña = PasswordField("Contraseña", validators=[DataRequired(), Length(min=6)])
    confirmar = PasswordField("Confirmar contraseña", validators=[DataRequired(), EqualTo("contraseña")])
    telefono = StringField("Teléfono", validators=[DataRequired(), Length(min=7, max=50)])
    direccion = StringField("Dirección", validators=[DataRequired(), Length(min=5)])
    submit = SubmitField("Registrarse")

class ResenaForm(FlaskForm):
    comentario = TextAreaField("Comentario", validators=[DataRequired(), Length(min=5, max=1000)])
    calificacion = IntegerField("Calificación (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField("Guardar reseña")

# ------------------------------------------------------------
# RUTAS PÚBLICAS y TIENDA (cliente ve USD)
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/tienda")
def tienda():
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("index"))

    productos = []
    try:
        q = "SELECT id, nombre, descripcion, precio, imagen_url, stock FROM productos;"
        res = conn.run(q)
        for r in res:
            # precio guardado en BD en COP; mantenemos entero o Decimal según venga
            try:
                precio_cop = parse_price_db(r[3]).quantize(Decimal('1'))
                precio_cop_int = int(precio_cop)
            except Exception:
                precio_cop_int = 0
            productos.append({
                "id": r[0],
                "nombre": r[1],
                "descripcion": r[2],
                "precio": precio_cop_int,  # COP entero
                "imagen_url": r[4],
                "stock": r[5]
            })
    except Exception as e:
        print("❌ Error al cargar tienda:", e)
        flash("Error al mostrar los productos.", "danger")
    finally:
        try: conn.close()
        except: pass

    # mostrar precios solo a usuarios autenticados (cliente)
    mostrar_precios = current_user.is_authenticated
    return render_template("tienda.html", productos=productos, mostrar_precios=mostrar_precios)


# ------------------------------------------------------------
# REGISTRO
# ------------------------------------------------------------
@app.route("/registro", methods=["GET", "POST"])
def registro():
    form = RegistroForm()
    if form.validate_on_submit():
        correo = form.correo.data.lower().strip()
        nombre_completo = form.nombre_completo.data.strip()
        telefono = form.telefono.data.strip()
        direccion = form.direccion.data.strip()

        conn = get_connection()
        if not conn:
            flash("Error de conexión con la base de datos.", "danger")
            return redirect(url_for("registro"))
        try:
            check_q = "SELECT id FROM usuarios WHERE correo = :correo;"
            existing = conn.run(check_q, correo=correo)
            if existing:
                flash("Ya existe una cuenta con ese correo.", "warning")
                conn.close()
                return redirect(url_for("registro"))
            hashed = bcrypt.hashpw(form.contraseña.data.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            insert_q = """
                INSERT INTO usuarios
                (nombre_usuario, correo, contraseña, rol, nombre_completo, telefono, direccion)
                VALUES (:nombre_usuario, :correo, :contraseña, :rol, :nombre_completo, :telefono, :direccion)
                RETURNING id;
            """
            nombre_usuario = correo.split("@")[0]
            res = conn.run(insert_q,
                           nombre_usuario=nombre_usuario,
                           correo=correo,
                           contraseña=hashed,
                           rol="cliente",
                           nombre_completo=nombre_completo,
                           telefono=telefono,
                           direccion=direccion)
            conn.commit()
            new_id = res[0][0] if res else None
            conn.close()
            flash("Cuenta creada exitosamente. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("login"))
        except Exception as e:
            try: conn.rollback()
            except: pass
            try: conn.close()
            except: pass
            print("❌ Error al registrar usuario:", e)
            flash("Ocurrió un error interno al registrar. Revisa la consola.", "danger")
            return redirect(url_for("registro"))
    return render_template("registro.html", form=form)


# ------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        correo = form.correo.data.lower().strip()
        conn = get_connection()
        if not conn:
            flash("Error de conexión con la base de datos.", "danger")
            return redirect(url_for("login"))
        try:
            query = """
                SELECT id, nombre_usuario, correo, contraseña, rol, nombre_completo
                FROM usuarios
                WHERE correo = :correo;
            """
            result = conn.run(query, correo=correo)
            conn.close()
            if not result:
                flash("Correo o contraseña incorrectos.", "danger")
                return redirect(url_for("login"))
            user_data = result[0]
            stored_hash_raw = user_data[3]
            if isinstance(stored_hash_raw, str):
                stored_hash = stored_hash_raw.encode("utf-8")
            else:
                stored_hash = stored_hash_raw
            if bcrypt.checkpw(form.contraseña.data.encode("utf-8"), stored_hash):
                user = Usuario(user_data[0], user_data[1], user_data[2], user_data[4])
                try:
                    user.nombre_completo = user_data[5] or user_data[1]
                except Exception:
                    user.nombre_completo = user_data[1]
                login_user(user)
                # sincronizar con session (tu código lo requiere)
                session["usuario_id"] = user.id
                session["rol"] = user.rol
                session["usuario_nombre"] = getattr(user, "nombre_completo", user.nombre_usuario)
                session.modified = True
                flash("Inicio de sesión exitoso.", "success")
                print(f"✅ Login correcto: {user.correo} (rol={getattr(user,'rol',None)})")
                rol_lower = (getattr(user, "rol", "") or "").lower()
                if rol_lower == "admin":
                    return redirect(url_for("dashboard_admin"))
                else:
                    return redirect(url_for("dashboard_usuario"))
            else:
                flash("Correo o contraseña incorrectos.", "danger")
                print("❌ Contraseña inválida para:", correo)
                return redirect(url_for("login"))
        except Exception as e:
            try: conn.close()
            except: pass
            print("❌ Error durante el proceso de login:", e)
            flash("Error interno en el login. Revisa la consola.", "danger")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)


# ------------------------------------------------------------
# LOGOUT
# ------------------------------------------------------------
@app.route("/logout")
@login_required
def logout():
    try:
        logout_user()
    except Exception as e:
        print("⚠️ Warning logout_user():", e)
    session.pop("usuario_id", None)
    session.pop("rol", None)
    session.pop("usuario_nombre", None)
    session.pop("carrito", None)
    session.modified = True
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------
# PANEL_CLIENTE y SUBRUTAS (respetando tus rutas)
# ------------------------------------------------------------
@app.route("/dashboard_usuario")
@login_required
def dashboard_usuario():
    if current_user.rol != "cliente":
        flash("Acceso restringido al panel de clientes.", "danger")
        return redirect(url_for("index"))
    return render_template("dashboard_usuario.html", usuario=current_user)


@app.route("/pedidos")
@login_required
def pedidos():
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    return render_template("pedidos.html", usuario=current_user)


@app.route("/historial")
@login_required
def historial():
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    return render_template("historial.html", usuario=current_user)


@app.route("/resenas")
@login_required
def resenas():
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    conn = get_connection()
    reseñas = []
    try:
        q = """
            SELECT r.id, r.id_producto, r.comentario, r.calificacion, r.fecha, p.nombre
            FROM reseñas r
            JOIN productos p ON p.id = r.id_producto
            WHERE r.id_usuario = :uid
            ORDER BY r.fecha DESC;
        """
        res = conn.run(q, uid=current_user.id)
        for row in res:
            reseñas.append({
                "id": row[0],
                "id_producto": row[1],
                "comentario": row[2],
                "calificacion": row[3],
                "fecha": row[4],
                "producto_nombre": row[5]
            })
    except Exception as e:
        print("❌ Error al listar reseñas:", e)
        flash("Error al obtener reseñas.", "danger")
    finally:
        try: conn.close()
        except: pass
    return render_template("resenas.html", reseñas=reseñas)


@app.route("/resenas/crear/<int:product_id>", methods=["GET", "POST"])
@login_required
def crear_resena(product_id):
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    form = ResenaForm()
    conn = get_connection()
    producto = None
    try:
        p = conn.run("SELECT id, nombre FROM productos WHERE id = :id;", id=product_id)
        producto = p[0] if p else None
    except Exception as e:
        print("❌ Error al obtener producto para reseña:", e)
    finally:
        try: conn.close()
        except: pass
    if not producto:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("tienda"))
    if form.validate_on_submit():
        conn = get_connection()
        try:
            insert_q = """
                INSERT INTO reseñas (id_usuario, id_producto, comentario, calificacion)
                VALUES (:uid, :pid, :comentario, :calificacion)
                RETURNING id;
            """
            res = conn.run(insert_q,
                           uid=current_user.id,
                           pid=product_id,
                           comentario=form.comentario.data.strip(),
                           calificacion=int(form.calificacion.data))
            conn.commit()
            new_id = res[0][0] if res else None
            flash("Reseña guardada. ¡Gracias por tu opinión!", "success")
            return redirect(url_for("resenas"))
        except Exception as e:
            print("❌ Error al guardar reseña:", e)
            try: conn.rollback()
            except: pass
            flash("No se pudo guardar la reseña.", "danger")
        finally:
            try: conn.close()
            except: pass
    return render_template("resena_form.html", form=form, producto_nombre=producto[1] if producto else "")


# ================================
# PERFIL DEL USUARIO (EDITAR)
# ================================
@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_usuario"))

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        telefono = request.form.get("telefono", "").strip()
        direccion = request.form.get("direccion", "").strip()
        if not nombre:
            flash("El nombre no puede estar vacío.", "warning")
            try: conn.close()
            except: pass
            return redirect(url_for("perfil"))
        try:
            update_q = """
                UPDATE usuarios
                SET nombre_completo = :nombre,
                    telefono = :telefono,
                    direccion = :direccion
                WHERE id = :id;
            """
            conn.run(update_q,
                     nombre=nombre,
                     telefono=telefono,
                     direccion=direccion,
                     id=current_user.id)
            conn.commit()
            session["usuario_nombre"] = nombre
            try:
                current_user.nombre_completo = nombre
            except Exception:
                pass
            flash("Perfil actualizado correctamente.", "success")
            try: conn.close()
            except: pass
            return redirect(url_for("perfil"))
        except Exception as e:
            print("❌ Error al actualizar perfil:", e)
            try:
                conn.rollback()
            except:
                pass
            flash("No se pudo actualizar el perfil. Revisa la consola.", "danger")
            try: conn.close()
            except: pass
            return redirect(url_for("perfil"))

    try:
        q = """
            SELECT nombre_completo, correo, telefono, direccion
            FROM usuarios
            WHERE id = :id;
        """
        res = conn.run(q, id=current_user.id)
        datos = {"nombre": "", "correo": "", "telefono": "", "direccion": ""}
        if res and len(res) > 0:
            row = res[0]
            datos["nombre"] = row[0] or ""
            datos["correo"] = row[1] or ""
            datos["telefono"] = row[2] or ""
            datos["direccion"] = row[3] or ""
    except Exception as e:
        print("❌ Error al cargar perfil:", e)
        flash("Error cargando datos del perfil.", "danger")
        try: conn.close()
        except: pass
        return redirect(url_for("dashboard_usuario"))
    finally:
        try: conn.close()
        except: pass

    return render_template("perfil.html", datos=datos)


# ------------------------------------------------------------
# DETALLE DE PRODUCTO + RESEÑAS (cliente ve USD)
# ------------------------------------------------------------
@app.route("/producto/<int:id>")
def producto(id):
    conn = get_connection()
    producto = None
    reseñas = []
    try:
        res = conn.run(
            "SELECT id, nombre, descripcion, precio, imagen_url, stock FROM productos WHERE id = :id;",
            id=id
        )
        if res:
            p = res[0]
            precio_cop = parse_price_db(p[3]).quantize(Decimal('1'))
            producto = {
                "id": p[0],
                "nombre": p[1],
                "descripcion": p[2],
                "precio": int(precio_cop),
                "imagen_url": p[4],
                "stock": p[5] if len(p) > 5 else None
            }
        # cargar reseñas
        res_r = conn.run("""
            SELECT r.comentario, u.nombre_completo, r.fecha, r.calificacion
            FROM reseñas r
            JOIN usuarios u ON r.id_usuario = u.id
            WHERE r.id_producto = :id
            ORDER BY r.fecha DESC;
        """, id=id)
        for rr in res_r:
            reseñas.append({
                "comentario": rr[0],
                "nombre_completo": rr[1],
                "fecha": rr[2],
                "calificacion": rr[3]
            })
    except Exception as e:
        print("❌ Error al obtener producto o reseñas:", e)
    finally:
        try: conn.close()
        except: pass
    mostrar_precios = current_user.is_authenticated and current_user.rol == "cliente"
    return render_template("producto.html", producto=producto, reseñas=reseñas, mostrar_precios=mostrar_precios)


# ------------------------------------------------------------
# DASHBOARD ADMIN (admin ve COP)
# ------------------------------------------------------------
@app.route("/dashboard_admin")
@login_required
def dashboard_admin():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    conn = get_connection()
    products = []
    try:
        res = conn.run("SELECT id, nombre, precio, stock FROM productos ORDER BY id;")
        for r in res:
            products.append({
                "id": r[0],
                "nombre": r[1],
                "precio": int(parse_price_db(r[2]).quantize(Decimal('1'))),
                "stock": r[3]
            })
    except Exception as e:
        print("❌ Error dashboard_admin:", e)
    finally:
        try: conn.close()
        except: pass
    stats = {"total_usuarios": 0, "total_productos": len(products), "total_pedidos": 0, "reseñas_pendientes": 0}
    return render_template("dashboard_admin.html", stats=stats, products=products)


# ==========================================
# CARRITO DE COMPRAS (cliente ve USD in display)
# ==========================================
@app.route("/carrito", methods=["GET", "POST"])
def carrito():
    if request.method == "POST":
        carrito = session.get("carrito", [])
        changed = False
        for item in carrito:
            key = f"qty_{item['id']}"
            if key in request.form:
                try:
                    new_q = int(request.form.get(key, item.get("cantidad", 1)))
                    if new_q <= 0:
                        item["cantidad"] = 0
                    else:
                        item["cantidad"] = new_q
                    changed = True
                except Exception:
                    pass
        carrito = [i for i in carrito if int(i.get("cantidad", 1)) > 0]
        session["carrito"] = carrito
        session.modified = True
        if changed:
            flash("Carrito actualizado.", "success")
        return redirect(url_for("carrito"))
    carrito = session.get("carrito", [])
    total = sum(int(item["precio"]) * int(item["cantidad"]) for item in carrito)
    return render_template("carrito.html", carrito=carrito, total=total)


@app.route("/agregar_carrito/<int:producto_id>", methods=["GET", "POST"])
@login_required
def agregar_carrito(producto_id):
    qty = 1
    try:
        if request.method == "POST":
            qty = int(request.form.get("cantidad", 1))
        else:
            qty = int(request.args.get("cantidad", 1))
    except Exception:
        qty = 1
    if qty < 1:
        qty = 1
    conn = get_connection()
    try:
        res = conn.run("SELECT id, nombre, precio, imagen_url, stock FROM productos WHERE id = :id;", id=producto_id)
        if not res:
            flash("Producto no encontrado.", "warning")
            return redirect(url_for("tienda"))
        row = res[0]
        prod_id = row[0]
        nombre = row[1]
        precio_raw = row[2]
        imagen = row[3]
        stock = row[4] if len(row) > 4 else None
        precio_dec = parse_price_db(precio_raw).quantize(Decimal('1'))
        precio_int = int(precio_dec)
        if stock is not None:
            if stock <= 0:
                flash("Producto sin stock.", "warning")
                return redirect(url_for("tienda"))
            if qty > stock:
                flash(f"Sólo hay {stock} unidades disponibles.", "warning")
                qty = int(stock)
        producto = {
            "id": int(prod_id),
            "nombre": nombre,
            "precio": precio_int,  # COP
            "imagen_url": imagen,
            "cantidad": int(qty)
        }
        carrito = session.get("carrito", [])
        found = False
        for item in carrito:
            if int(item.get("id")) == producto["id"]:
                item["cantidad"] = int(item.get("cantidad", 1)) + producto["cantidad"]
                found = True
                break
        if not found:
            carrito.append(producto)
        session["carrito"] = carrito
        session.modified = True
        flash(f"{producto['cantidad']} x {producto['nombre']} agregado(s) al carrito.", "success")
    except Exception as e:
        print("❌ Error al agregar al carrito:", e)
        flash("No se pudo agregar el producto al carrito.", "danger")
    finally:
        try: conn.close()
        except: pass
    return redirect(url_for("carrito"))


@app.route("/vaciar_carrito")
def vaciar_carrito():
    session["carrito"] = []
    session.modified = True
    return redirect(url_for("carrito"))


# ==============================
# CHECKOUT (SIMULACIÓN DE COMPRA) - guarda pedidos y descuenta stock
# ==============================
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not current_user.is_authenticated and "usuario_id" not in session:
        flash("Debes iniciar sesión para continuar.", "warning")
        return redirect(url_for("login"))
    carrito = session.get("carrito", [])
    if not carrito:
        flash("Tu carrito está vacío.", "info")
        return redirect(url_for("tienda"))
    total = sum(int(item["precio"]) * int(item["cantidad"]) for item in carrito)  # total en COP (int)
    if request.method == "POST":
        try:
            conn = get_connection()
            cursor = conn.cursor()
            id_usuario = int(session.get("usuario_id") or current_user.get_id())
            # verificar stock
            for item in carrito:
                pid = int(item["id"])
                q_needed = int(item["cantidad"])
                row = conn.run("SELECT stock FROM productos WHERE id = :id;", id=pid)
                stock = row[0][0] if row and row[0] and len(row[0])>0 else None
                if stock is not None and q_needed > stock:
                    flash(f"No hay suficiente stock de {item['nombre']}. Disponible: {stock}", "warning")
                    try: cursor.close()
                    except: pass
                    try: conn.close()
                    except: pass
                    return redirect(url_for("carrito"))
            # insertar pedido (nota: columna fecha_pedido en tu BD)
            insert_pedido = """
                INSERT INTO pedidos (id_usuario, fecha_pedido, total, estado)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """
            cursor.execute(insert_pedido, (id_usuario, datetime.now(), total, "Pendiente"))
            pedido_id = cursor.fetchone()[0]
            # insertar detalle y actualizar stock
            insert_detalle = """
                INSERT INTO detalle_pedidos (id_pedido, id_producto, cantidad, subtotal)
                VALUES (%s, %s, %s, %s);
            """
            update_stock = "UPDATE productos SET stock = stock - %s WHERE id = %s;"
            for item in carrito:
                pid = int(item["id"])
                qty = int(item["cantidad"])
                unit_price = int(item["precio"])
                subtotal = unit_price * qty
                cursor.execute(insert_detalle, (pedido_id, pid, qty, subtotal))
                cursor.execute(update_stock, (qty, pid))
            conn.commit()
            try: cursor.close()
            except: pass
            try: conn.close()
            except: pass
            # vaciar carrito
            session["carrito"] = []
            session.modified = True
            flash("Compra realizada con éxito (simulada).", "success")
            return redirect(url_for("checkout_success"))
        except Exception as e:
            print("❌ Error en checkout:", e)
            try:
                conn.rollback()
            except:
                pass
            try:
                cursor.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
            flash("Error procesando el pedido.", "danger")
            return redirect(url_for("carrito"))
    # GET -> mostrar resumen con total (mostrado en USD para cliente mediante filtro 'usd' en template)
    return render_template("checkout.html", carrito=carrito, total=total)


@app.route("/checkout_success")
def checkout_success():
    if not current_user.is_authenticated and "usuario_id" not in session:
        flash("Debes iniciar sesión para ver esta página.", "warning")
        return redirect(url_for("login"))
    return render_template("checkout_success.html")


# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    # debug=True facilita desarrollo local pero no usar en producción
    app.run(debug=True)