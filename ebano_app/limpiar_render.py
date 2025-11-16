from bd_config import get_connection
import os

# Asegúrate que estés usando Render en .env
db_host = os.getenv("DB_HOST")
print(f"Conectando a: {db_host}")

if "render.com" not in db_host:
    print("❌ ERROR: No estás apuntando a Render!")
    print(f"DB_HOST actual: {db_host}")
    exit(1)

conn = get_connection()
if not conn:
    print("❌ No se pudo conectar")
    exit(1)

cursor = conn.cursor()

# Limpiar datos en orden (respetando foreign keys)
print("🗑️  Limpiando BD de Render...")

try:
    cursor.execute("DELETE FROM detalle_pedidos;")
    print("✅ detalle_pedidos eliminados")
    
    cursor.execute("DELETE FROM resenas;")
    print("✅ resenas eliminadas")
    
    cursor.execute("DELETE FROM pedidos;")
    print("✅ pedidos eliminados")
    
    cursor.execute("DELETE FROM productos;")
    print("✅ productos eliminados")
    
    cursor.execute("DELETE FROM usuarios;")
    print("✅ usuarios eliminados")
    
    conn.commit()
    print("\n✅ BD de Render limpiada correctamente")
except Exception as e:
    print(f"❌ Error: {e}")
    conn.rollback()
finally:
    cursor.close()
    conn.close()