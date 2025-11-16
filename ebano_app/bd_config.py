import pg8000
import os
import ssl
from dotenv import load_dotenv

# ---------------------------------------------------------
# CARGA DE VARIABLES DE ENTORNO (.env)
# ---------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------
# FUNCIÓN DE CONEXIÓN
# ---------------------------------------------------------
def get_connection():
    """
    Establece una conexión con la base de datos PostgreSQL
    usando las variables de entorno definidas en el archivo .env.
    Incluye soporte SSL para conexiones remotas (Render).
    Devuelve el objeto de conexión si es exitosa, o None si falla.
    """
    try:
        # Crear contexto SSL para conexiones remotas (Render requiere SSL)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connection = pg8000.connect(
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 5432)),
            ssl_context=ssl_context  # ← CRÍTICO: SSL requerido por Render
        )
        print("✅ Conexión a la base de datos establecida correctamente.")
        return connection
    except Exception as e:
        print("❌ Error al conectar a la base de datos:", e)
        import traceback
        traceback.print_exc()
        return None


# ---------------------------------------------------------
# PRUEBA DIRECTA DE CONEXIÓN (solo si se ejecuta este archivo)
# ---------------------------------------------------------
if __name__ == "__main__":
    conn = get_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            print("Versión del servidor PostgreSQL:", version[0])
            cursor.close()
            conn.close()
        except Exception as e:
            print("❌ Error en la prueba:", e)