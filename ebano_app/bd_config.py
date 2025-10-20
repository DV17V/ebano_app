import pg8000
import os
from dotenv import load_dotenv

# ---------------------------------------------------------
# CARGA DE VARIABLES DE ENTORNO (.env)
# ---------------------------------------------------------
# Esto permite leer los valores definidos en tu archivo .env
load_dotenv()

# ---------------------------------------------------------
# FUNCIÓN DE CONEXIÓN
# ---------------------------------------------------------
def get_connection():
    """
    Establece una conexión con la base de datos PostgreSQL
    usando las variables de entorno definidas en el archivo .env.
    Devuelve el objeto de conexión si es exitosa, o None si falla.
    """
    try:
        connection = pg8000.connect(
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 5432))
        )
        print("✅ Conexión a la base de datos establecida correctamente.")
        return connection
    except Exception as e:
        print("❌ Error al conectar a la base de datos:", e)
        return None


# ---------------------------------------------------------
# PRUEBA DIRECTA DE CONEXIÓN (solo si se ejecuta este archivo)
# ---------------------------------------------------------
if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("Versión del servidor PostgreSQL:", conn.run("SELECT version();")[0][0])
        conn.close()

