# ============================================================
# app.py  |  ÉBANO — Fase 1: Login / Registro / Tienda
#          COP -> USD (currencyapi.com v3) - Cache 12h
# ============================================================
from datetime import datetime
import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import jwt
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
app.secret_key = os.getenv("SECRET_KEY", "clave_segura_ebano_default")
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv("WTF_CSRF_SECRET_KEY", app.secret_key)

# 🆕 NUEVAS LÍNEAS PARA PRODUCCIÓN
app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------------------------------------------------
# CONFIGURACIÓN DE TASA DE CAMBIO (COP -> USD)
# ------------------------------------------------------------
EXCHANGE_TTL_SECONDS = int(os.getenv("EXCHANGE_TTL_SECONDS", 43200))  # 12 horas
EXCHANGE_API_URL = os.getenv("EXCHANGE_API_URL", "https://api.currencyapi.com/v3/latest")
CURRENCY_API_KEY = os.getenv("CURRENCY_API_KEY", "")
EXCHANGE_REQUEST_TIMEOUT = int(os.getenv("EXCHANGE_REQUEST_TIMEOUT", 8))

# Tasa de fallback (si la API falla): 1 COP = 0.00026 USD (~3,846 COP = 1 USD)
FALLBACK_COP_TO_USD = Decimal("0.00026")

# Caché simple en memoria
_app_exchange_cache = {
    "timestamp": 0.0,
    "cop_to_usd": None,
    "usd_to_cop": None
}

# -------------------------
# Helpers de precios
# -------------------------
def parse_price_db(value):
    """
    Normaliza valores provenientes de la BD a Decimal (COP).
    PostgreSQL con NUMERIC(10,2) siempre devuelve Decimal directamente.
    """
    if value is None:
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    
    # Si viene como string, limpiar y convertir
    try:
        cleaned = str(value).strip().replace(",", "")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal(0)


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


def get_cop_to_usd_rate():
    """
    Obtiene la tasa COP -> USD desde currencyapi.com v3.
    Respuesta esperada:
    {
      "meta": {"last_updated_at": "2025-11-14T23:59:59Z"},
      "data": {
        "USD": {"code": "USD", "value": 0.0002662073}
      }
    }
    
    Si falla, devuelve tasa de fallback predefinida.
    Cache: 12 horas (configurable en .env)
    """
    now = time.time()
    
    # Verificar caché
    if (_app_exchange_cache["cop_to_usd"] is not None and 
        (now - _app_exchange_cache["timestamp"]) < EXCHANGE_TTL_SECONDS):
        return _app_exchange_cache["cop_to_usd"], _app_exchange_cache["usd_to_cop"]
    
    # Validar API key
    if not CURRENCY_API_KEY:
        print("⚠️ CURRENCY_API_KEY no configurada en .env, usando tasa de fallback")
        usd_to_cop = (Decimal('1') / FALLBACK_COP_TO_USD).quantize(Decimal('0.01'))
        return FALLBACK_COP_TO_USD, usd_to_cop
    
    # Preparar request a currencyapi.com v3
    params = {
        "apikey": CURRENCY_API_KEY,
        "base_currency": "COP",
        "currencies": "USD"
    }
    
    try:
        print(f"🔄 Obteniendo tasa COP->USD desde {EXCHANGE_API_URL}...")
        resp = requests.get(EXCHANGE_API_URL, params=params, timeout=EXCHANGE_REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        # Validar estructura de respuesta de currencyapi.com
        if "data" not in data or "USD" not in data["data"]:
            raise ValueError("Respuesta inválida de currencyapi.com: falta 'data.USD'")
        
        rate_value = data["data"]["USD"]["value"]
        cop_to_usd = Decimal(str(rate_value))
        
        if cop_to_usd <= 0:
            raise ValueError("Tasa COP->USD inválida (cero o negativa)")
        
        usd_to_cop = (Decimal('1') / cop_to_usd).quantize(Decimal('0.01'))
        
        # Guardar en caché
        _app_exchange_cache["timestamp"] = now
        _app_exchange_cache["cop_to_usd"] = cop_to_usd
        _app_exchange_cache["usd_to_cop"] = usd_to_cop
        
        print(f"✅ Tasa actualizada: 1 COP = {cop_to_usd} USD | 1 USD = {usd_to_cop} COP")
        return cop_to_usd, usd_to_cop
        
    except requests.RequestException as e:
        print(f"❌ Error HTTP al obtener tasa: {e}")
    except (ValueError, KeyError) as e:
        print(f"❌ Error parseando respuesta de API: {e}")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
    
    # Fallback: usar tasa fija
    print(f"⚠️ Usando tasa de fallback: 1 COP = {FALLBACK_COP_TO_USD} USD")
    usd_to_cop = (Decimal('1') / FALLBACK_COP_TO_USD).quantize(Decimal('0.01'))
    return FALLBACK_COP_TO_USD, usd_to_cop


def cop_to_usd_decimal(cop_value):
    """
    Convierte un valor en COP (Decimal/int/str) a Decimal USD con 2 decimales.
    """
    cop_dec = parse_price_db(cop_value)
    cop_to_usd, _ = get_cop_to_usd_rate()
    usd = (cop_dec * cop_to_usd).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return usd


def format_usd(value):
    """
    Para mostrar en plantillas: recibe valor en COP y devuelve "$10.95 USD"
    Si hay error, devuelve mensaje claro.
    """
    try:
        usd = cop_to_usd_decimal(value)
        return "${:,.2f} USD".format(float(usd))
    except Exception as e:
        print(f"⚠️ format_usd error: {e}")
        return "USD no disponible"


# Registrar filtros Jinja
app.jinja_env.filters['cop'] = format_cop
app.jinja_env.filters['usd'] = format_usd


# ------------------------------------------------------------
# RUTA DE DEBUGGING: Ver tasa actual
# ------------------------------------------------------------
@app.route("/api/rate")
def api_rate():
    """
    Devuelve JSON con la tasa actual COP->USD y USD->COP.
    Útil para debugging.
    """
    try:
        cop_to_usd_dec, usd_to_cop_dec = get_cop_to_usd_rate()
        return jsonify({
            "success": True,
            "cop_to_usd": float(cop_to_usd_dec),
            "usd_to_cop": float(usd_to_cop_dec),
            "cached_at": _app_exchange_cache["timestamp"],
            "cache_ttl_seconds": EXCHANGE_TTL_SECONDS,
            "source": "currencyapi.com" if CURRENCY_API_KEY else "fallback"
        })
    except Exception as err:
        return jsonify({
            "success": False,
            "error": str(err)
        }), 500


# ------------------------------------------------------------
# MODELO DE USUARIO PARA FLASK-LOGIN
# ------------------------------------------------------------
class Usuario(UserMixin):
    def __init__(self, id, nombre_usuario, correo, rol):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.correo = correo
        self.rol = rol


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
        print(f"❌ Error load_user: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
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
# RUTAS PÚBLICAS y TIENDA
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
            try:
                precio_cop = parse_price_db(r[3]).quantize(Decimal('1'))
                precio_cop_int = int(precio_cop)
            except Exception:
                precio_cop_int = 0
            
            productos.append({
                "id": r[0],
                "nombre": r[1],
                "descripcion": r[2],
                "precio": precio_cop_int,
                "imagen_url": r[4],
                "stock": r[5]
            })
    except Exception as e:
        print(f"❌ Error al cargar tienda: {e}")
        flash("Error al mostrar los productos.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass

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
            try:
                conn.rollback()
            except:
                pass
            try:
                conn.close()
            except:
                pass
            print(f"❌ Error al registrar usuario: {e}")
            flash("Ocurrió un error interno al registrar.", "danger")
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
            
            pwd_input = form.contraseña.data
            
            # Verificar contraseña
            is_password_correct = bcrypt.checkpw(pwd_input.encode("utf-8"), stored_hash)

            if is_password_correct:
                user = Usuario(user_data[0], user_data[1], user_data[2], user_data[4])
                try:
                    user.nombre_completo = user_data[5] or user_data[1]
                except Exception:
                    user.nombre_completo = user_data[1]
                
                login_user(user)
                
                session["usuario_id"] = user.id
                session["rol"] = user.rol
                session["usuario_nombre"] = getattr(user, "nombre_completo", user.nombre_usuario)
                session.modified = True
                
                flash("Inicio de sesión exitoso.", "success")
                
                if user.rol.lower() == "admin":
                    return redirect(url_for("dashboard_admin"))
                else:
                    return redirect(url_for("dashboard_usuario"))
            else:
                flash("Correo o contraseña incorrectos.", "danger")
                return redirect(url_for("login"))
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                conn.close()
            except:
                pass
            flash("Error interno en el login.", "danger")
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
        print(f"⚠️ Warning logout_user(): {e}")
    
    session.pop("usuario_id", None)
    session.pop("rol", None)
    session.pop("usuario_nombre", None)
    session.pop("carrito", None)
    session.modified = True
    
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------
# PANEL CLIENTE
# ------------------------------------------------------------
@app.route("/dashboard_usuario")
@login_required
def dashboard_usuario():
    if current_user.rol != "cliente":
        flash("Acceso restringido al panel de clientes.", "danger")
        return redirect(url_for("index"))
    return render_template("dashboard_usuario.html", usuario=current_user)


# ============================================================
# SECCIÓN: MIS PEDIDOS E HISTORIAL
# ============================================================

@app.route("/pedidos")
@login_required
def pedidos():
    """
    Muestra los pedidos activos del usuario (Pendiente, En proceso, Enviado).
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    pedidos_activos = []
    
    try:
        # Consultar pedidos activos (NO entregados ni cancelados)
        query = """
            SELECT p.id, p.fecha_pedido, p.total, p.estado
            FROM pedidos p
            WHERE p.id_usuario = :uid 
            AND p.estado NOT IN ('Entregado', 'Cancelado')
            ORDER BY p.fecha_pedido DESC;
        """
        res = conn.run(query, uid=current_user.id)
        
        for row in res:
            pedido_id = row[0]
            
            # Obtener detalle de productos del pedido
            detalle_query = """
                SELECT dp.cantidad, dp.subtotal, pr.nombre, pr.imagen_url
                FROM detalle_pedidos dp
                JOIN productos pr ON pr.id = dp.id_producto
                WHERE dp.id_pedido = :pid;
            """
            detalle_res = conn.run(detalle_query, pid=pedido_id)
            
            productos = []
            for det in detalle_res:
                productos.append({
                    "nombre": det[2],
                    "cantidad": det[0],
                    "subtotal": int(parse_price_db(det[1]).quantize(Decimal('1'))),
                    "imagen_url": det[3]
                })
            
            pedidos_activos.append({
                "id": pedido_id,
                "fecha": row[1],
                "total": int(parse_price_db(row[2]).quantize(Decimal('1'))),
                "estado": row[3],
                "productos": productos
            })
        
        print(f"✅ Usuario {current_user.id}: {len(pedidos_activos)} pedidos activos")
        
    except Exception as e:
        print(f"❌ Error al obtener pedidos: {e}")
        import traceback
        traceback.print_exc()
        flash("Error al cargar tus pedidos.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("pedidos.html", pedidos=pedidos_activos, usuario=current_user)

# ------------------------------------------------------------
# HISTORIAL DE PEDIDOS
# ------------------------------------------------------------
@app.route("/historial")
@login_required
def historial():
    """
    Muestra el historial de pedidos completados (Entregado, Cancelado).
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    pedidos_historial = []
    
    try:
        # Consultar pedidos completados
        query = """
            SELECT p.id, p.fecha_pedido, p.total, p.estado
            FROM pedidos p
            WHERE p.id_usuario = :uid 
            AND p.estado IN ('Entregado', 'Cancelado')
            ORDER BY p.fecha_pedido DESC;
        """
        res = conn.run(query, uid=current_user.id)
        
        for row in res:
            pedido_id = row[0]
            
            # Obtener detalle de productos del pedido
            detalle_query = """
                SELECT dp.cantidad, dp.subtotal, dp.id_producto, pr.nombre, pr.imagen_url
                FROM detalle_pedidos dp
                JOIN productos pr ON pr.id = dp.id_producto
                WHERE dp.id_pedido = :pid;
            """
            detalle_res = conn.run(detalle_query, pid=pedido_id)
            
            productos = []
            for det in detalle_res:
                productos.append({
                    "id_producto": det[2],
                    "nombre": det[3],
                    "cantidad": det[0],
                    "subtotal": int(parse_price_db(det[1]).quantize(Decimal('1'))),
                    "imagen_url": det[4]
                })
            
            pedidos_historial.append({
                "id": pedido_id,
                "fecha": row[1],
                "total": int(parse_price_db(row[2]).quantize(Decimal('1'))),
                "estado": row[3],
                "productos": productos
            })
        
        print(f"✅ Usuario {current_user.id}: {len(pedidos_historial)} pedidos en historial")
        
    except Exception as e:
        print(f"❌ Error al obtener historial: {e}")
        import traceback
        traceback.print_exc()
        flash("Error al cargar tu historial.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("historial.html", pedidos=pedidos_historial, usuario=current_user)

# ------------------------------------------------------------
# VOLVER A COMPRAR
# ------------------------------------------------------------
@app.route("/recomprar/<int:pedido_id>")
@login_required
def recomprar(pedido_id):
    """
    Agrega todos los productos de un pedido anterior al carrito.
    Informa al usuario si algún producto no tiene stock disponible.
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    
    try:
        # Verificar que el pedido pertenece al usuario
        check_query = "SELECT id FROM pedidos WHERE id = :pid AND id_usuario = :uid;"
        check_res = conn.run(check_query, pid=pedido_id, uid=current_user.id)
        
        if not check_res:
            flash("Pedido no encontrado.", "warning")
            try:
                conn.close()
            except:
                pass
            return redirect(url_for("historial"))
        
        # Obtener productos del pedido
        detalle_query = """
            SELECT dp.id_producto, dp.cantidad, pr.nombre, pr.precio, pr.imagen_url, pr.stock
            FROM detalle_pedidos dp
            JOIN productos pr ON pr.id = dp.id_producto
            WHERE dp.id_pedido = :pid;
        """
        detalle_res = conn.run(detalle_query, pid=pedido_id)
        
        carrito = session.get("carrito", [])
        productos_agregados = 0
        productos_sin_stock = []
        
        for det in detalle_res:
            id_producto = det[0]
            cantidad_pedido = det[1]
            nombre = det[2]
            precio_raw = det[3]
            imagen = det[4]
            stock = det[5]
            
            precio_dec = parse_price_db(precio_raw).quantize(Decimal('1'))
            precio_int = int(precio_dec)
            
            # Validar stock disponible
            if stock is not None and stock <= 0:
                print(f"⚠️ Producto {nombre} sin stock, omitido")
                productos_sin_stock.append(nombre)
                continue
            
            cantidad_a_agregar = min(cantidad_pedido, stock) if stock else cantidad_pedido
            
            # Buscar si ya está en el carrito
            found = False
            for item in carrito:
                if int(item.get("id")) == id_producto:
                    item["cantidad"] = int(item.get("cantidad", 1)) + cantidad_a_agregar
                    found = True
                    break
            
            if not found:
                carrito.append({
                    "id": id_producto,
                    "nombre": nombre,
                    "precio": precio_int,
                    "imagen_url": imagen,
                    "cantidad": cantidad_a_agregar
                })
            
            productos_agregados += 1
        
        session["carrito"] = carrito
        session.modified = True
        
        print(f"✅ {productos_agregados} productos del pedido {pedido_id} agregados al carrito")
        
        # Mensajes informativos según el resultado
        if productos_sin_stock and productos_agregados == 0:
            # Todos los productos están sin stock
            productos_faltantes = ", ".join(productos_sin_stock)
            if len(productos_sin_stock) == 1:
                flash(f"El producto '{productos_faltantes}' no está disponible actualmente.", "warning")
            else:
                flash(f"Los siguientes productos no están disponibles: {productos_faltantes}.", "warning")
        
        elif productos_agregados > 0:
            # Se agregó al menos un producto
            mensaje_base = f"Se agregaron {productos_agregados} producto(s) al carrito."
            
            if productos_sin_stock:
                # Algunos productos se agregaron, otros no
                productos_faltantes = ", ".join(productos_sin_stock)
                if len(productos_sin_stock) == 1:
                    mensaje_final = f"{mensaje_base} El producto '{productos_faltantes}' no está disponible actualmente."
                else:
                    mensaje_final = f"{mensaje_base} Los siguientes productos no están disponibles: {productos_faltantes}."
                flash(mensaje_final, "warning")
            else:
                # Todos los productos se agregaron correctamente
                flash(mensaje_base, "success")
        
        else:
            # Caso raro: no hay productos sin stock pero tampoco se agregó nada
            flash("No se pudo agregar ningún producto al carrito.", "danger")
        
    except Exception as e:
        print(f"❌ Error al recomprar pedido {pedido_id}: {e}")
        import traceback
        traceback.print_exc()
        flash("Error al agregar productos al carrito.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return redirect(url_for("carrito"))

# ------------------------------------------------------------
# PANEL RESEÑAS
# ------------------------------------------------------------

@app.route("/resenas")
@login_required
def resenas():
    """
    Muestra todas las reseñas del usuario actual.
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    reseñas = []
    
    try:
        q = """
            SELECT r.id, r.id_producto, r.comentario, r.calificacion, r.fecha, p.nombre
            FROM resenas r
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
        
        print(f"✅ Usuario {current_user.id}: {len(reseñas)} reseñas encontradas")
        
    except Exception as e:
        print(f"❌ Error al listar reseñas: {e}")
        import traceback
        traceback.print_exc()
        flash("Error al obtener reseñas.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("resenas.html", reseñas=reseñas)

# ------------------------------------------------------------
# CREAR RESEÑA
# ------------------------------------------------------------

@app.route("/resenas/crear/<int:product_id>", methods=["GET", "POST"])
@login_required
def crear_resena(product_id):
    """
    Crea una nueva reseña para un producto.
    """
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
        print(f"❌ Error al obtener producto para reseña: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
    
    if not producto:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("tienda"))
    
    if form.validate_on_submit():
        conn = get_connection()
        try:
            # Verificar si ya existe una reseña de este usuario para este producto
            check_q = """
                SELECT id FROM resenas 
                WHERE id_usuario = :uid AND id_producto = :pid;
            """
            existing = conn.run(check_q, uid=current_user.id, pid=product_id)
            
            if existing:
                flash("Ya has escrito una reseña para este producto. Puedes editarla desde 'Mis reseñas'.", "warning")
                try:
                    conn.close()
                except:
                    pass
                return redirect(url_for("resenas"))
            
            insert_q = """
                INSERT INTO resenas (id_usuario, id_producto, comentario, calificacion)
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
            
            print(f"✅ Reseña creada: id={new_id}, producto={product_id}, usuario={current_user.id}")
            
            flash("Reseña guardada. ¡Gracias por tu opinión!", "success")
            return redirect(url_for("producto", id=product_id))
            
        except Exception as e:
            print(f"❌ Error al guardar reseña: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.rollback()
            except:
                pass
            flash("No se pudo guardar la reseña.", "danger")
        finally:
            try:
                conn.close()
            except:
                pass
    
    return render_template("resena_form.html", form=form, producto_nombre=producto[1] if producto else "", editar=False)


# ------------------------------------------------------------
# EDITAR RESEÑA
# ------------------------------------------------------------

@app.route("/resenas/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_resena(id):
    """
    Edita una reseña existente (solo si pertenece al usuario actual).
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    resena_actual = None
    producto_nombre = ""
    
    try:
        # Obtener la reseña y verificar que pertenece al usuario
        q = """
            SELECT r.id, r.id_producto, r.comentario, r.calificacion, p.nombre
            FROM resenas r
            JOIN productos p ON p.id = r.id_producto
            WHERE r.id = :rid AND r.id_usuario = :uid;
        """
        res = conn.run(q, rid=id, uid=current_user.id)
        
        if not res:
            flash("Reseña no encontrada o no tienes permiso para editarla.", "danger")
            try:
                conn.close()
            except:
                pass
            return redirect(url_for("resenas"))
        
        resena_actual = res[0]
        producto_nombre = resena_actual[4]
        
    except Exception as e:
        print(f"❌ Error al obtener reseña: {e}")
        flash("Error al cargar la reseña.", "danger")
        try:
            conn.close()
        except:
            pass
        return redirect(url_for("resenas"))
    finally:
        try:
            conn.close()
        except:
            pass
    
    form = ResenaForm()
    
    if request.method == "GET":
        # Pre-llenar el formulario con datos actuales
        form.comentario.data = resena_actual[2]
        form.calificacion.data = resena_actual[3]
    
    if form.validate_on_submit():
        conn = get_connection()
        try:
            update_q = """
                UPDATE resenas
                SET comentario = :comentario, calificacion = :calificacion
                WHERE id = :rid AND id_usuario = :uid;
            """
            conn.run(update_q,
                     comentario=form.comentario.data.strip(),
                     calificacion=int(form.calificacion.data),
                     rid=id,
                     uid=current_user.id)
            conn.commit()
            
            print(f"✅ Reseña {id} actualizada por usuario {current_user.id}")
            
            flash("Reseña actualizada correctamente.", "success")
            return redirect(url_for("resenas"))
            
        except Exception as e:
            print(f"❌ Error al actualizar reseña: {e}")
            import traceback
            traceback.print_exc()
            try:
                conn.rollback()
            except:
                pass
            flash("No se pudo actualizar la reseña.", "danger")
        finally:
            try:
                conn.close()
            except:
                pass
    
    return render_template("resena_form.html", form=form, producto_nombre=producto_nombre, editar=True)

# ------------------------------------------------------------
# BORRAR RESEÑA
# ------------------------------------------------------------

@app.route("/resenas/borrar/<int:id>", methods=["POST"])
@login_required
def borrar_resena(id):
    """
    Elimina una reseña (solo si pertenece al usuario actual).
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    
    try:
        # Verificar que la reseña pertenece al usuario
        check_q = "SELECT id FROM resenas WHERE id = :rid AND id_usuario = :uid;"
        res = conn.run(check_q, rid=id, uid=current_user.id)
        
        if not res:
            flash("Reseña no encontrada o no tienes permiso para eliminarla.", "danger")
            try:
                conn.close()
            except:
                pass
            return redirect(url_for("resenas"))
        
        # Eliminar la reseña
        delete_q = "DELETE FROM resenas WHERE id = :rid AND id_usuario = :uid;"
        conn.run(delete_q, rid=id, uid=current_user.id)
        conn.commit()
        
        print(f"✅ Reseña {id} eliminada por usuario {current_user.id}")
        
        flash("Reseña eliminada correctamente.", "success")
        
    except Exception as e:
        print(f"❌ Error al eliminar reseña: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        flash("No se pudo eliminar la reseña.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return redirect(url_for("resenas"))

# ============================================================
# SECCIÓN: PERFIL DE USUARIO (DATOS + CONTRASEÑA)
# ============================================================

@app.route("/perfil", methods=["GET"])
@login_required
def perfil():
    """
    Muestra el perfil del usuario con sus datos personales.
    Solo para clientes.
    """
    if current_user.rol != "cliente":
        flash("Acceso restringido al perfil de clientes.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_usuario"))

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
        print(f"❌ Error al cargar perfil: {e}")
        import traceback
        traceback.print_exc()
        flash("Error cargando datos del perfil.", "danger")
        try:
            conn.close()
        except:
            pass
        return redirect(url_for("dashboard_usuario"))
    finally:
        try:
            conn.close()
        except:
            pass

    return render_template("perfil.html", datos=datos)


@app.route("/perfil/editar-datos", methods=["POST"])
@login_required
def perfil_editar_datos():
    """
    Actualiza los datos personales del usuario (nombre, teléfono, dirección).
    Solo para clientes.
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    nombre = request.form.get("nombre", "").strip()
    telefono = request.form.get("telefono", "").strip()
    direccion = request.form.get("direccion", "").strip()
    
    if not nombre:
        flash("El nombre no puede estar vacío.", "warning")
        return redirect(url_for("perfil"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
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
        
        # Actualizar sesión
        session["usuario_nombre"] = nombre
        try:
            current_user.nombre_completo = nombre
        except Exception:
            pass
        
        print(f"✅ Datos personales actualizados: usuario {current_user.id}")
        
        flash("Datos personales actualizados correctamente.", "success")
        
    except Exception as e:
        print(f"❌ Error al actualizar datos: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        flash("No se pudo actualizar los datos.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return redirect(url_for("perfil"))


@app.route("/perfil/cambiar-contrasena", methods=["POST"])
@login_required
def perfil_cambiar_contrasena():
    """
    Cambia la contraseña del usuario.
    Valida la contraseña actual antes de actualizar.
    Solo para clientes.
    """
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    
    contrasena_actual = request.form.get("contrasena_actual", "").strip()
    contrasena_nueva = request.form.get("contrasena_nueva", "").strip()
    contrasena_confirmar = request.form.get("contrasena_confirmar", "").strip()
    
    # Validaciones
    if not all([contrasena_actual, contrasena_nueva, contrasena_confirmar]):
        flash("Todos los campos de contraseña son obligatorios.", "warning")
        return redirect(url_for("perfil"))
    
    if contrasena_nueva != contrasena_confirmar:
        flash("La nueva contraseña y su confirmación no coinciden.", "danger")
        return redirect(url_for("perfil"))
    
    if len(contrasena_nueva) < 6:
        flash("La nueva contraseña debe tener al menos 6 caracteres.", "warning")
        return redirect(url_for("perfil"))
    
    if contrasena_actual == contrasena_nueva:
        flash("La nueva contraseña debe ser diferente a la actual.", "warning")
        return redirect(url_for("perfil"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("perfil"))
    
    try:
        # Obtener contraseña actual de la BD
        q = "SELECT contraseña FROM usuarios WHERE id = :id;"
        res = conn.run(q, id=current_user.id)
        
        if not res:
            flash("Error al verificar usuario.", "danger")
            try:
                conn.close()
            except:
                pass
            return redirect(url_for("perfil"))
        
        stored_hash_raw = res[0][0]
        
        if isinstance(stored_hash_raw, str):
            stored_hash = stored_hash_raw.encode("utf-8")
        else:
            stored_hash = stored_hash_raw
        
        # Verificar contraseña actual
        if not bcrypt.checkpw(contrasena_actual.encode("utf-8"), stored_hash):
            flash("La contraseña actual es incorrecta.", "danger")
            try:
                conn.close()
            except:
                pass
            return redirect(url_for("perfil"))
        
        # Hashear nueva contraseña
        nueva_hash = bcrypt.hashpw(contrasena_nueva.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        # Actualizar en BD
        update_q = "UPDATE usuarios SET contraseña = :contraseña WHERE id = :id;"
        conn.run(update_q, contraseña=nueva_hash, id=current_user.id)
        conn.commit()
        
        print(f"✅ Contraseña cambiada: usuario {current_user.id}")
        
        flash("Contraseña actualizada correctamente. Por seguridad, vuelve a iniciar sesión.", "success")
        
        # Cerrar sesión por seguridad (opcional pero recomendado)
        try:
            logout_user()
        except:
            pass
        session.clear()
        
        return redirect(url_for("login"))
        
    except Exception as e:
        print(f"❌ Error al cambiar contraseña: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        flash("No se pudo cambiar la contraseña.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return redirect(url_for("perfil"))


# ------------------------------------------------------------
# DETALLE DE PRODUCTO
# ------------------------------------------------------------
@app.route("/producto/<int:id>")
def producto(id):
    """
    Muestra el detalle de un producto con sus reseñas.
    """
    conn = get_connection()
    producto = None
    reseñas = []
    
    try:
        # Obtener producto
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
        
        # Cargar reseñas del producto
        if producto:
            query_resenas = """
                SELECT r.comentario, u.nombre_completo, r.fecha, r.calificacion
                FROM resenas r
                JOIN usuarios u ON r.id_usuario = u.id
                WHERE r.id_producto = :id
                ORDER BY r.fecha DESC;
            """
            res_r = conn.run(query_resenas, id=id)
            
            for rr in res_r:
                reseñas.append({
                    "comentario": rr[0],
                    "nombre_completo": rr[1],
                    "fecha": rr[2],
                    "calificacion": rr[3]
                })
            
            print(f"✅ Producto {id}: {len(reseñas)} reseñas encontradas")
        
    except Exception as e:
        print(f"❌ Error al obtener producto o reseñas: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            conn.close()
        except:
            pass
    
    if not producto:
        flash("Producto no encontrado.", "warning")
        return redirect(url_for("tienda"))
    
    mostrar_precios = current_user.is_authenticated and current_user.rol == "cliente"
    return render_template("producto.html", producto=producto, reseñas=reseñas, mostrar_precios=mostrar_precios)


# ------------------------------------------------------------
# DASHBOARD ADMIN (ve precios en COP)
# ------------------------------------------------------------
@app.route("/dashboard_admin")
@login_required
def dashboard_admin():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    products = []
    total_usuarios = 0
    total_resenas = 0
    
    try:
        # Contar usuarios clientes
        res_usuarios = conn.run("SELECT COUNT(*) FROM usuarios WHERE rol = :rol;", rol="cliente")
        total_usuarios = res_usuarios[0][0] if res_usuarios else 0
        
        # Contar reseñas
        res_resenas = conn.run("SELECT COUNT(*) FROM resenas;")
        total_resenas = res_resenas[0][0] if res_resenas else 0
        
        # Contar pedidos
        res_pedidos = conn.run("SELECT COUNT(*) FROM pedidos;")
        total_pedidos = res_pedidos[0][0] if res_pedidos else 0
        
        # Cargar productos
        res = conn.run("SELECT id, nombre, precio, stock FROM productos ORDER BY id;")
        for r in res:
            products.append({
                "id": r[0],
                "nombre": r[1],
                "precio": int(parse_price_db(r[2]).quantize(Decimal('1'))),
                "stock": r[3]
            })
    except Exception as e:
        print(f"❌ Error dashboard_admin: {e}")
    finally:
        try:
            conn.close()
        except:
            pass
    
    stats = {
        "total_usuarios": total_usuarios,
        "total_productos": len(products),
        "total_pedidos": total_pedidos,
        "reseñas_pendientes": total_resenas
    }
    
    return render_template("dashboard_admin.html", stats=stats, products=products)

# ------------------------------------------------------------
# DASHBOARD DE ANALÍTICA (METABASE) - SOLO ADMIN
# ------------------------------------------------------------
@app.route("/admin/dashboard_analitica")
@login_required
def dashboard_analitica():
    """
    Muestra el dashboard de Metabase embebido con token JWT.
    Solo accesible para administradores.
    """
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    # Configuración de Metabase desde variables de entorno
    METABASE_SITE_URL = os.getenv("METABASE_PROD_URL", "http://localhost:3000")
    METABASE_SECRET_KEY = os.getenv("METABASE_PROD_SECRET_KEY", "406ff0d4a4bc2e1a609a5b76e753a914c24499de468709190b98b4a26b9db8ad")
    
    # Validar que las variables existen
    if not METABASE_SITE_URL or METABASE_SITE_URL == "http://localhost:3000":
        flash("Error: Metabase no está configurado. Verifica las variables de entorno.", "danger")
        return redirect(url_for("dashboard_admin"))
    
    if not METABASE_SECRET_KEY:
        flash("Error: Falta la clave secreta de Metabase. Verifica METABASE_PROD_SECRET_KEY en .env", "danger")
        return redirect(url_for("dashboard_admin"))
    
    try:
        # Crear payload con expiración de 2 HORAS (7200 segundos)
        payload = {
            "resource": {"dashboard": 1},
            "params": {},
            "exp": round(time.time()) + (60 * 120)
        }
        
        # Generar token JWT
        token = jwt.encode(payload, METABASE_SECRET_KEY, algorithm="HS256")
        
        # Construir URL del iframe
        metabase_url = f"{METABASE_SITE_URL}/embed/dashboard/{token}#bordered=true&titled=true&theme=night"
        
        print(f"✅ Token JWT generado para Metabase dashboard")
        
        return render_template("dashboard_analitica.html", metabase_url=metabase_url)
        
    except Exception as e:
        print(f"❌ Error generando token Metabase: {e}")
        import traceback
        traceback.print_exc()
        flash("Error al generar el dashboard de analítica. Intenta nuevamente.", "danger")
        return redirect(url_for("dashboard_admin"))

# ------------------------------------------------------------
# GESTIONAR USUARIOS (ADMIN) - Listado de clientes
# ------------------------------------------------------------
@app.route("/admin/gestionar_usuarios", methods=["GET"])
@login_required
def gestionar_usuarios():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_admin"))
    
    usuarios = []
    try:
        # Obtener todos los usuarios con rol 'cliente' ordenados por fecha de registro
        res = conn.run("""
            SELECT id, nombre_usuario, correo, nombre_completo, telefono, direccion, fecha_registro
            FROM usuarios
            WHERE rol = :rol
            ORDER BY fecha_registro DESC;
        """, rol="cliente")
        
        for row in res:
            usuarios.append({
                "id": row[0],
                "nombre_usuario": row[1],
                "correo": row[2],
                "nombre_completo": row[3] or row[1],
                "telefono": row[4] or "No registrado",
                "direccion": row[5] or "No registrada",
                "fecha_registro": row[6]
            })
        
        print(f"✅ Listado de usuarios: {len(usuarios)} clientes encontrados")
    
    except Exception as e:
        print(f"❌ Error al obtener usuarios: {e}")
        flash("Error al cargar los usuarios.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("gestionar_usuarios.html", usuarios=usuarios)


# ------------------------------------------------------------
# GESTIONAR RESEÑAS (ADMIN) - Todas las reseñas
# ------------------------------------------------------------
@app.route("/admin/gestionar_resenas", methods=["GET"])
@login_required
def gestionar_resenas():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_admin"))
    
    resenas = []
    try:
        # Obtener todas las reseñas con información de usuario y producto
        res = conn.run("""
            SELECT r.id, r.id_usuario, u.nombre_completo, u.correo, r.id_producto, 
                   p.nombre as producto_nombre, r.comentario, r.calificacion, r.fecha
            FROM resenas r
            JOIN usuarios u ON r.id_usuario = u.id
            JOIN productos p ON r.id_producto = p.id
            ORDER BY r.fecha DESC;
        """)
        
        for row in res:
            resenas.append({
                "id": row[0],
                "id_usuario": row[1],
                "usuario_nombre": row[2],
                "usuario_correo": row[3],
                "id_producto": row[4],
                "producto_nombre": row[5],
                "comentario": row[6],
                "calificacion": row[7],
                "fecha": row[8]
            })
        
        print(f"✅ Listado de reseñas: {len(resenas)} reseñas encontradas")
    
    except Exception as e:
        print(f"❌ Error al obtener reseñas: {e}")
        flash("Error al cargar las reseñas.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("gestionar_resenas.html", resenas=resenas)


# ------------------------------------------------------------
# GESTIONAR PEDIDOS (ADMIN) - Todos los pedidos
# ------------------------------------------------------------
@app.route("/admin/gestionar_pedidos", methods=["GET"])
@login_required
def gestionar_pedidos():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_admin"))
    
    pedidos = []
    try:
        # Obtener todos los pedidos con información de usuario
        res = conn.run("""
            SELECT p.id, p.id_usuario, u.nombre_completo, u.correo, p.fecha_pedido, 
                   p.total, p.estado
            FROM pedidos p
            JOIN usuarios u ON p.id_usuario = u.id
            ORDER BY p.fecha_pedido DESC;
        """)
        
        for row in res:
            pedidos.append({
                "id": row[0],
                "id_usuario": row[1],
                "usuario_nombre": row[2],
                "usuario_correo": row[3],
                "fecha_pedido": row[4],
                "total": int(parse_price_db(row[5]).quantize(Decimal('1'))),
                "estado": row[6]
            })
        
        print(f"✅ Listado de pedidos: {len(pedidos)} pedidos encontrados")
    
    except Exception as e:
        print(f"❌ Error al obtener pedidos: {e}")
        flash("Error al cargar los pedidos.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return render_template("gestionar_pedidos.html", pedidos=pedidos)


# ------------------------------------------------------------
# GESTIONAR PRODUCTOS (ADMIN) - Inventario
# ------------------------------------------------------------
@app.route("/admin/gestionar_productos", methods=["GET", "POST"])
@login_required
def gestionar_productos():
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))
    
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("dashboard_admin"))
    
    try:
        # Si es POST, actualizar un producto específico
        if request.method == "POST":
            producto_id = request.form.get("producto_id", "").strip()
            nuevo_stock = request.form.get("stock", "").strip()
            nuevo_precio = request.form.get("precio", "").strip()
            
            if not producto_id or not nuevo_stock:
                flash("Datos incompletos.", "warning")
                return redirect(url_for("gestionar_productos"))
            
            try:
                producto_id = int(producto_id)
                nuevo_stock = int(nuevo_stock)
                
                if nuevo_stock < 0:
                    flash("El stock no puede ser negativo.", "warning")
                    return redirect(url_for("gestionar_productos"))
                
                # Actualizar stock
                conn.run("UPDATE productos SET stock = :stock WHERE id = :id;", stock=nuevo_stock, id=producto_id)
                
                # Actualizar precio si se proporciona
                if nuevo_precio:
                    try:
                        nuevo_precio_dec = Decimal(nuevo_precio)
                        if nuevo_precio_dec < 0:
                            flash("El precio no puede ser negativo.", "warning")
                            return redirect(url_for("gestionar_productos"))
                        conn.run("UPDATE productos SET precio = :precio WHERE id = :id;", precio=nuevo_precio_dec, id=producto_id)
                    except (InvalidOperation, ValueError):
                        flash("Precio inválido.", "warning")
                        return redirect(url_for("gestionar_productos"))
                
                conn.commit()
                flash("Producto actualizado correctamente.", "success")
                return redirect(url_for("gestionar_productos"))
            
            except ValueError:
                flash("Stock y precio deben ser números válidos.", "warning")
                return redirect(url_for("gestionar_productos"))
            except Exception as e:
                print(f"❌ Error al actualizar producto {producto_id}: {e}")
                try:
                    conn.rollback()
                except:
                    pass
                flash("Error al actualizar el producto.", "danger")
                return redirect(url_for("gestionar_productos"))
        
        # GET: cargar todos los productos para la tabla
        productos = []
        try:
            res = conn.run("SELECT id, nombre, precio, stock FROM productos ORDER BY id;")
            for r in res:
                productos.append({
                    "id": r[0],
                    "nombre": r[1],
                    "precio": int(parse_price_db(r[2]).quantize(Decimal('1'))),
                    "stock": r[3]
                })
        except Exception as e:
            print(f"❌ Error al cargar productos: {e}")
            flash("Error al cargar los productos.", "danger")
        
        return render_template("gestionar_productos.html", productos=productos)
    
    except Exception as e:
        print(f"❌ Error en gestionar_productos: {e}")
        flash("Error al gestionar productos.", "danger")
        return redirect(url_for("dashboard_admin"))
    finally:
        try:
            conn.close()
        except:
            pass


# ------------------------------------------------------------
# CARRITO DE COMPRAS
# ------------------------------------------------------------
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
            "precio": precio_int,
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
        print(f"❌ Error al agregar al carrito: {e}")
        flash("No se pudo agregar el producto al carrito.", "danger")
    finally:
        try:
            conn.close()
        except:
            pass
    
    return redirect(url_for("carrito"))


@app.route("/vaciar_carrito")
def vaciar_carrito():
    session["carrito"] = []
    session.modified = True
    return redirect(url_for("carrito"))


# ------------------------------------------------------------
# CHECKOUT (SIMULACIÓN DE COMPRA)
# ------------------------------------------------------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not current_user.is_authenticated and "usuario_id" not in session:
        flash("Debes iniciar sesión para continuar.", "warning")
        return redirect(url_for("login"))
    
    carrito = session.get("carrito", [])
    if not carrito:
        flash("Tu carrito está vacío.", "info")
        return redirect(url_for("tienda"))
    
    total = sum(int(item["precio"]) * int(item["cantidad"]) for item in carrito)
    
    if request.method == "POST":
        try:
            conn = get_connection()
            cursor = conn.cursor()
            id_usuario = int(session.get("usuario_id") or current_user.get_id())
            
            # ← NUEVO: Validación completa de stock ANTES de procesar
            productos_sin_stock = []
            productos_stock_insuficiente = []
            
            for item in carrito:
                pid = int(item["id"])
                q_needed = int(item["cantidad"])
                
                # Obtener stock actual y nombre del producto
                row = conn.run("SELECT stock, nombre FROM productos WHERE id = :id;", id=pid)
                
                if not row or not row[0]:
                    productos_sin_stock.append(item["nombre"])
                    continue
                
                stock_actual = row[0][0]
                nombre_producto = row[0][1]
                
                # Validar si hay stock suficiente
                if stock_actual is None:
                    # Si stock es NULL, permitir la compra (stock ilimitado)
                    continue
                elif stock_actual <= 0:
                    productos_sin_stock.append(nombre_producto)
                elif q_needed > stock_actual:
                    productos_stock_insuficiente.append(
                        f"{nombre_producto} (disponible: {stock_actual}, solicitaste: {q_needed})"
                    )
            
            # Si hay productos sin stock o insuficientes, rechazar la compra
            if productos_sin_stock or productos_stock_insuficiente:
                try:
                    cursor.close()
                except:
                    pass
                try:
                    conn.close()
                except:
                    pass
                
                # Construir mensaje de error
                mensaje_error = "No se pudo procesar tu pedido. "
                
                if productos_sin_stock:
                    if len(productos_sin_stock) == 1:
                        mensaje_error += f"El producto '{productos_sin_stock[0]}' ya no tiene stock disponible. "
                    else:
                        lista_productos = "', '".join(productos_sin_stock)
                        mensaje_error += f"Los productos '{lista_productos}' ya no tienen stock disponible. "
                
                if productos_stock_insuficiente:
                    if len(productos_stock_insuficiente) == 1:
                        mensaje_error += f"{productos_stock_insuficiente[0]}. "
                    else:
                        for prod_info in productos_stock_insuficiente:
                            mensaje_error += f"{prod_info}. "
                
                mensaje_error += "Por favor actualiza tu carrito."
                
                flash(mensaje_error, "danger")
                print(f"❌ Compra rechazada: {mensaje_error}")
                return redirect(url_for("carrito"))
            
            # ← Si llegamos aquí, todos los productos tienen stock suficiente
            # Proceder con la compra
            
            # Insertar pedido
            insert_pedido = """
                INSERT INTO pedidos (id_usuario, fecha_pedido, total, estado)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """
            cursor.execute(insert_pedido, (id_usuario, datetime.now(), total, "Pendiente"))
            pedido_id = cursor.fetchone()[0]
            
            # Insertar detalle y actualizar stock
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
            
            try:
                cursor.close()
            except:
                pass
            try:
                conn.close()
            except:
                pass
            
            # Vaciar carrito
            session["carrito"] = []
            session.modified = True
            
            print(f"✅ Pedido #{pedido_id} procesado correctamente para usuario {id_usuario}")
            flash("Compra realizada con éxito (simulada).", "success")
            return redirect(url_for("checkout_success"))
            
        except Exception as e:
            print(f"❌ Error en checkout: {e}")
            import traceback
            traceback.print_exc()
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
            flash("Error procesando el pedido. Por favor intenta de nuevo.", "danger")
            return redirect(url_for("carrito"))
    
    return render_template("checkout.html", carrito=carrito, total=total)

@app.route("/checkout_success")
def checkout_success():
    if not current_user.is_authenticated and "usuario_id" not in session:
        flash("Debes iniciar sesión para ver esta página.", "warning")
        return redirect(url_for("login"))
    return render_template("checkout_success.html")

# ------------------------------------------------------------
# MANEJADORES DE ERRORES
# ------------------------------------------------------------
@app.errorhandler(404)
def page_not_found(e):
    """
    Maneja errores 404 (página no encontrada).
    Muestra la plantilla personalizada 404.html.
    """
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_server_error(e):
    """
    Maneja errores 500 (error interno del servidor).
    Opcional: puedes crear una plantilla 500.html si quieres.
    """
    print(f"❌ Error 500: {e}")
    return render_template('404.html'), 500  # Reutiliza 404.html por ahora

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    # Obtener puerto desde variable de entorno (para Render/Heroku/etc)
    port = int(os.environ.get("PORT", 5000))
    
    # En producción, Render usará gunicorn, no este comando
    # Este bloque solo se usa para desarrollo local
    debug_mode = os.getenv("FLASK_ENV") != "production"
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)