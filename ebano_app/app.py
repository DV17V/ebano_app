# ============================================================
# app.py  |  ÉBANO — Fase 1: Login / Registro / Tienda
# ============================================================
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, UserMixin, current_user
)
from dotenv import load_dotenv
import os
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from bd_config import get_connection
import bcrypt

# ------------------------------------------------------------
# CONFIGURACIÓN FLASK
# ------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.getenv("clave_segura_ebano", "DB_PASS" )  # reemplázala por una clave real (en .env si prefieres)
app.config['WTF_CSRF_SECRET_KEY'] = "clave_segura_ebano"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# ------------------------------------------------------------
# MODELO DE USUARIO PARA FLASK-LOGIN
# ------------------------------------------------------------
class Usuario(UserMixin):
    def __init__(self, id, nombre_usuario, correo, rol):
        self.id = id
        self.nombre_usuario = nombre_usuario
        self.correo = correo
        self.rol = rol

# -------------------------
# RESEÑAS - CRUD para clientes
# -------------------------
class ReseñaForm(FlaskForm):
    comentario = TextAreaField("Comentario", validators=[DataRequired(), Length(min=5, max=1000)])
    calificacion = IntegerField("Calificación (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField("Guardar reseña")

# Cargar usuario desde la BD por id
@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    if conn:
        query = "SELECT id, nombre_usuario, correo, rol FROM usuarios WHERE id = :id;"
        result = conn.run(query, id=user_id)
        conn.close()
        if result:
            u = result[0]
            return Usuario(u[0], u[1], u[2], u[3])
    return None

# ------------------------------------------------------------
# FORMULARIOS (WTForms)
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

# ------------------------------------------------------------
# RUTAS PÚBLICAS
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


# ------------------------------------------------------------
# TIENDA
# ------------------------------------------------------------
@app.route("/tienda")
def tienda():
    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.", "danger")
        return redirect(url_for("index"))

    try:
        query = """
            SELECT id, nombre, descripcion, precio, imagen_url, stock
            FROM productos;
        """
        result = conn.run(query)
        conn.close()

        # Convertir filas a diccionarios legibles
        productos = []
        for row in result:
            productos.append({
                "id": row[0],
                "nombre": row[1],
                "descripcion": row[2],
                "precio": row[3],
                "imagen_url": row[4],
                "stock": row[5]
            })

        # Mostrar precios solo si el usuario está autenticado
        mostrar_precios = current_user.is_authenticated

        return render_template("tienda.html", productos=productos, mostrar_precios=mostrar_precios)

    except Exception as e:
        print("❌ Error al cargar tienda:", e)
        conn.close()
        flash("Error al mostrar los productos.", "danger")
        return redirect(url_for("index"))

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
            # 1) Verificar si ya existe el correo
            check_q = "SELECT id FROM usuarios WHERE correo = :correo;"
            existing = conn.run(check_q, correo=correo)
            if existing:
                flash("Ya existe una cuenta con ese correo.", "warning")
                conn.close()
                return redirect(url_for("registro"))

            # 2) Hashear la contraseña con bcrypt
            hashed = bcrypt.hashpw(form.contraseña.data.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

            # 3) Insertar usuario (usar parámetros con nombre, compatibles con pg8000)
            insert_q = """
                INSERT INTO usuarios
                (nombre_usuario, correo, contraseña, rol, nombre_completo, telefono, direccion)
                VALUES (:nombre_usuario, :correo, :contraseña, :rol, :nombre_completo, :telefono, :direccion)
                RETURNING id;
            """
            nombre_usuario = correo.split("@")[0]

            result = conn.run(
                insert_q,
                nombre_usuario=nombre_usuario,
                correo=correo,
                contraseña=hashed,
                rol="cliente",
                nombre_completo=nombre_completo,
                telefono=telefono,
                direccion=direccion
            )

            # 4) ✅ IMPORTANTÍSIMO: confirmar la transacción antes de cerrar
            conn.commit()

            new_id = result[0][0] if result else None
            conn.close()

            flash("Cuenta creada exitosamente. Ya puedes iniciar sesión.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            # En caso de fallo, hacer rollback para dejar la BD consistente
            try:
                conn.rollback()
            except Exception:
                pass
            conn.close()
            print("❌ Error al registrar usuario:", e)
            flash("Ocurrió un error interno al registrar. Revisa la consola.", "danger")
            return redirect(url_for("registro"))

    return render_template("registro.html", form=form)

# ------------------------------------------------------------
# LOGIN
# ------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login seguro — reemplaza la versión previa.
    Usa pg8000 placeholders con nombre, attach de nombre_completo al objeto Usuario,
    login_user() y redirección por rol a dashboard correspondiente.
    """
    form = LoginForm()
    if form.validate_on_submit():
        correo = form.correo.data.lower().strip()
        conn = get_connection()
        if not conn:
            flash("Error de conexión con la base de datos.", "danger")
            return redirect(url_for("login"))

        try:
            # Obtener datos del usuario (incluye nombre_completo)
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
            # stored_hash_raw puede venir como str; asegurar bytes
            if isinstance(stored_hash_raw, str):
                stored_hash = stored_hash_raw.encode("utf-8")
            else:
                stored_hash = stored_hash_raw

            # Verificar contraseña
            if bcrypt.checkpw(form.contraseña.data.encode("utf-8"), stored_hash):
                # Crear objeto Usuario para flask-login
                user = Usuario(user_data[0], user_data[1], user_data[2], user_data[4])
                # Adjuntar nombre_completo si está disponible
                try:
                    user.nombre_completo = user_data[5] or user_data[1]
                except Exception:
                    user.nombre_completo = user_data[1]

                login_user(user)
                flash("Inicio de sesión exitoso.", "success")

                # DEBUG: registrar en consola (útil para verificar flujo)
                print(f"✅ Login correcto: {user.correo} (rol={getattr(user,'rol',None)})")

                # Redirección por rol (segura, sin suposiciones)
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
            # Asegurar cierre / logging y no romper la app con trace innecesario
            try:
                conn.close()
            except Exception:
                pass
            print("❌ Error durante el proceso de login:", e)
            flash("Error interno en el login. Revisa la consola.", "danger")
            return redirect(url_for("login"))

    # GET o formulario no validado
    return render_template("login.html", form=form)


# ------------------------------------------------------------
# LOGOUT
# ------------------------------------------------------------
@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("index"))

# ------------------------------------------------------------
# PANEL_CLIENTE
# ------------------------------------------------------------
@app.route("/dashboard_usuario")
@login_required
def dashboard_usuario():
    # Solo los usuarios con rol cliente pueden acceder
    if current_user.rol != "cliente":
        flash("Acceso restringido al panel de clientes.", "danger")
        return redirect(url_for("index"))

    return render_template("dashboard_usuario.html", usuario=current_user)

# -----------------------------
# SUBRUTAS DEL DASHBOARD CLIENTE
# -----------------------------
@app.route("/pedidos")
@login_required
def pedidos():
    # Solo clientes
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    # Por ahora plantilla estática / estructura
    return render_template("pedidos.html", usuario=current_user)

@app.route("/historial")
@login_required
def historial():
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    return render_template("historial.html", usuario=current_user)

# -------------------------
# RESEÑAS - CRUD para clientes
# -------------------------
from wtforms import TextAreaField, IntegerField
from wtforms.validators import NumberRange

class ResenaForm(FlaskForm):
    comentario = TextAreaField("Comentario", validators=[DataRequired(), Length(min=5, max=1000)])
    calificacion = IntegerField("Calificación (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    submit = SubmitField("Guardar reseña")

@app.route("/resenas")
@login_required
def resenas():
    # Lista las reseñas del usuario (panel)
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
    # Obtener nombre de producto para mostrar en la plantilla
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

@app.route("/resenas/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_resena(id):
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))

    conn = get_connection()
    try:
        res = conn.run("SELECT id, id_usuario, id_producto, comentario, calificacion FROM reseñas WHERE id = :id;", id=id)
        if not res:
            flash("Reseña no encontrada.", "warning")
            return redirect(url_for("resenas"))
        row = res[0]
        # Sólo autor puede editar
        if row[1] != current_user.id:
            flash("No tienes permisos para editar esta reseña.", "danger")
            return redirect(url_for("resenas"))
        # cargar form con datos existentes
        form = ResenaForm(comentario=row[3], calificacion=row[4])
    except Exception as e:
        print("❌ Error al cargar reseña para editar:", e)
        flash("Error interno.", "danger")
        try: conn.close()
        except: pass
        return redirect(url_for("resenas"))
    finally:
        try: conn.close()
        except: pass

    if form.validate_on_submit():
        conn = get_connection()
        try:
            upd = """
                UPDATE reseñas SET comentario = :comentario, calificacion = :calificacion, fecha = CURRENT_TIMESTAMP
                WHERE id = :id;
            """
            conn.run(upd, comentario=form.comentario.data.strip(), calificacion=int(form.calificacion.data), id=id)
            conn.commit()
            flash("Reseña actualizada.", "success")
            return redirect(url_for("resenas"))
        except Exception as e:
            print("❌ Error al actualizar reseña:", e)
            try: conn.rollback()
            except: pass
            flash("No se pudo actualizar la reseña.", "danger")
        finally:
            try: conn.close()
            except: pass

    return render_template("resena_form.html", form=form, editar=True)

@app.route("/resenas/borrar/<int:id>", methods=["POST"])
@login_required
def borrar_resena(id):
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))

    conn = get_connection()
    try:
        res = conn.run("SELECT id, id_usuario FROM reseñas WHERE id = :id;", id=id)
        if not res:
            flash("Reseña no encontrada.", "warning")
            conn.close()
            return redirect(url_for("resenas"))
        if res[0][1] != current_user.id:
            flash("No tienes permiso para eliminar esta reseña.", "danger")
            conn.close()
            return redirect(url_for("resenas"))

        conn.run("DELETE FROM reseñas WHERE id = :id;", id=id)
        conn.commit()
        flash("Reseña eliminada.", "info")
    except Exception as e:
        print("❌ Error al borrar reseña:", e)
        try: conn.rollback()
        except: pass
        flash("No se pudo eliminar la reseña.", "danger")
    finally:
        try: conn.close()
        except: pass

    return redirect(url_for("resenas"))


# ------------------------------------------------------------
# GESTIONAR PERFIL (CLIENTE)
# ------------------------------------------------------------
@app.route("/perfil")
@login_required
def perfil():
    if current_user.rol != "cliente":
        flash("Acceso no autorizado.", "danger")
        return redirect(url_for("index"))
    return render_template("perfil.html", usuario=current_user)


# ===========================
# DETALLE DE PRODUCTO + RESEÑAS
# ===========================
@app.route("/producto/<int:id>")
def producto(id):
    conn = get_connection()
    producto = None
    resenas = []

    try:
        # Obtener información del producto
        res = conn.run(
            "SELECT id, nombre, descripcion, precio, imagen_url FROM productos WHERE id = :id;",
            id=id
        )
        if res:
            p = res[0]
            producto = {
                "id": p[0],
                "nombre": p[1],
                "descripcion": p[2],
                "precio": float(p[3]) if p[3] else 0.0,
                "imagen_url": p[4]
            }

        # ✅ Obtener reseñas vinculadas correctamente según tu tabla real
        resenas_query = """
            SELECT r.comentario, u.nombre_completo, r.fecha, r.calificacion
            FROM resenas r
            JOIN usuarios u ON r.id_usuario = u.id
            WHERE r.id_producto = :id
            ORDER BY r.fecha DESC;
        """
        resenas = conn.run(resenas_query, id=id)

        print(f"🟤 Reseñas encontradas: {len(resenas)}")

    except Exception as e:
        print("❌ Error al obtener producto o reseñas:", e)

    finally:
        try:
            conn.close()
        except:
            pass

    mostrar_precios = current_user.is_authenticated and current_user.rol == "cliente"

    return render_template(
        "producto.html",
        producto=producto,
        reseñas=resenas,
        mostrar_precios=mostrar_precios
    )


# ------------------------------------------------------------
# DASHBOARD ADMIN 
# ------------------------------------------------------------
@app.route("/dashboard_admin")
@login_required
def dashboard_admin():
    # Verificar que el usuario tenga rol de admin
    if current_user.rol != "admin":
        flash("No tienes permisos para acceder a esta sección.", "danger")
        return redirect(url_for("index"))

    # Datos simulados (luego se conectarán a la BD)
    stats = {
        "total_usuarios": 0,
        "total_productos": 0,
        "total_pedidos": 0,
        "reseñas_pendientes": 0
    }

    return render_template("dashboard_admin.html", stats=stats)

# ==========================================
# CARRITO DE COMPRAS (fase inicial)
# ==========================================

@app.route("/carrito")
def carrito():
    carrito = session.get("carrito", [])
    total = sum(item["precio"] * item["cantidad"] for item in carrito)
    return render_template("carrito.html", carrito=carrito, total=total)

@app.route("/agregar_carrito/<int:producto_id>")
@login_required
def agregar_carrito(producto_id):
    conn = get_connection()
    try:
        res = conn.run(
            "SELECT id, nombre, precio, imagen_url FROM productos WHERE id = :id;",
            id=producto_id
        )

        if not res:
            print(f"⚠️ Producto con id={producto_id} no encontrado.")
            return redirect(url_for("tienda"))

        p = res[0]
        producto = {
            "id": p[0],
            "nombre": p[1],
            "precio": float(p[2]),
            "imagen_url": p[3],
            "cantidad": 1
        }

        carrito = session.get("carrito", [])
        print(f"🛒 Carrito actual antes de agregar: {carrito}")

        # Verifica si ya existe
        for item in carrito:
            if item["id"] == producto_id:
                item["cantidad"] += 1
                print(f"🔁 Incrementando cantidad de {item['nombre']} a {item['cantidad']}")
                break
        else:
            carrito.append(producto)
            print(f"✅ Producto agregado: {producto['nombre']}")

        session["carrito"] = carrito
        session.modified = True
        print(f"🟢 Carrito actualizado: {session['carrito']}")

    except Exception as e:
        print("❌ Error al agregar al carrito:", e)
    finally:
        conn.close()

    return redirect(url_for("carrito"))

@app.route("/vaciar_carrito")
def vaciar_carrito():
    session["carrito"] = []
    return redirect(url_for("carrito"))

# ==============================
# CHECKOUT (SIMULACIÓN DE COMPRA)
# ==============================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para continuar con la compra.")
        return redirect(url_for("login"))

    carrito = session.get("carrito", [])
    if not carrito:
        flash("Tu carrito está vacío.")
        return redirect(url_for("tienda"))

    conn = get_connection()
    if not conn:
        flash("Error de conexión con la base de datos.")
        return redirect(url_for("carrito"))

    try:
        if request.method == "POST":
            total = sum(item["precio"] * item["cantidad"] for item in carrito)
            id_usuario = session["usuario_id"]

            # Crear pedido
            insert_pedido = """
                INSERT INTO pedidos (id_usuario, fecha, total, estado)
                VALUES (:id_usuario, :fecha, :total, :estado)
                RETURNING id;
            """
            pedido_result = conn.run(
                insert_pedido,
                id_usuario=id_usuario,
                fecha=datetime.now(),
                total=total,
                estado="Pendiente"
            )
            id_pedido = pedido_result[0][0]

            # Insertar detalle de pedido
            insert_detalle = """
                INSERT INTO detalle_pedidos (id_pedido, id_producto, cantidad, precio_unitario)
                VALUES (:id_pedido, :id_producto, :cantidad, :precio_unitario);
            """
            for item in carrito:
                conn.run(
                    insert_detalle,
                    id_pedido=id_pedido,
                    id_producto=item["id"],
                    cantidad=item["cantidad"],
                    precio_unitario=item["precio"]
                )

            conn.commit()
            conn.close()

            # Vaciar carrito
            session["carrito"] = []
            return redirect(url_for("checkout_success"))

        else:
            total = sum(item["precio"] * item["cantidad"] for item in carrito)
            return render_template("checkout.html", carrito=carrito, total=total)

    except Exception as e:
        conn.rollback()
        conn.close()
        print("❌ Error durante el checkout:", e)
        flash("Ocurrió un error al procesar el pedido.")
        return redirect(url_for("carrito"))


@app.route("/checkout_success")
def checkout_success():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("checkout_success.html")

# ------------------------------------------------------------
# MAIN
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
