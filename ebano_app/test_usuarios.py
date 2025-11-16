from bd_config import get_connection

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT id, correo, rol FROM usuarios;")
resultado = cursor.fetchall()
print("Usuarios encontrados:")
for row in resultado:
    print(row)
cursor.close()
conn.close()