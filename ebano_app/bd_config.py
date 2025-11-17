import pg8000
import os
import ssl
from contextlib import contextmanager
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
    
    - DESARROLLO (localhost): SIN SSL
    - PRODUCCIÓN (Render): CON SSL
    
    Devuelve el objeto de conexión si es exitosa, o None si falla.
    """
    try:
        # Obtener configuración de la BD
        db_host = os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASS")
        db_port = int(os.getenv("DB_PORT", 5432))
        
        # Determinar si es localhost o remoto
        is_localhost = db_host in ["localhost", "127.0.0.1"]
        
        # Configurar SSL según ambiente
        ssl_context = None
        if not is_localhost:
            # PRODUCCIÓN (Render o servidor remoto): SSL OBLIGATORIO
            print(f"🔒 Conectando a BD remota ({db_host}) CON SSL...")
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        else:
            # DESARROLLO (localhost): SIN SSL
            print(f"💻 Conectando a BD local ({db_host}) SIN SSL...")
        
        # Realizar conexión
        connection = pg8000.connect(
            database=db_name,
            user=db_user,
            password=db_pass,
            host=db_host,
            port=db_port,
            ssl_context=ssl_context  # None para local, ssl_context para remoto
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
            print("✅ Prueba de conexión exitosa")
        except Exception as e:
            print("❌ Error en la prueba:", e)
    else:
        print("❌ No se pudo establecer conexión")

# ---------------------------------------------------------
@contextmanager
def db_connection():
    """
    Context manager para manejar conexiones de BD automáticamente.
    
    Uso:
        with db_connection() as conn:
            result = conn.run("SELECT * FROM usuarios;")
    """
    conn = get_connection()
    if not conn:
        raise Exception("No se pudo establecer conexión con la BD")
    
    try:
        yield conn
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        raise e
    finally:
        try:
            conn.close()
        except:
            pass