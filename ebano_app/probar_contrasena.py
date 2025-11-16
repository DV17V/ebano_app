from bd_config import get_connection
import bcrypt

conn = get_connection()
cursor = conn.cursor()

correo = "Diego@udenar.edu.co"
cursor.execute("SELECT id, correo, contraseña FROM usuarios WHERE correo = %s;", (correo,))
resultado = cursor.fetchone()

if resultado:
    print(f"Usuario encontrado: {resultado[1]}")
    
    # Probar con TU contraseña
    pwd_prueba = "1234567890"  # ← REEMPLAZA AQUI
    pwd_bytes = pwd_prueba.encode("utf-8")
    stored_hash = resultado[2].encode("utf-8") if isinstance(resultado[2], str) else resultado[2]
    
    if bcrypt.checkpw(pwd_bytes, stored_hash):
        print(f"✅ Contraseña CORRECTA: {pwd_prueba}")
    else:
        print(f"❌ Contraseña INCORRECTA: {pwd_prueba}")
else:
    print(f"❌ Usuario no encontrado")

cursor.close()
conn.close()