"""
create_admin.py
Script para crear un usuario administrador inicial en la tabla `usuarios`.

Uso (Windows, con venv activado):
PS ...\ebano_app> python create_admin.py
"""

import getpass
import bcrypt
from bd_config import get_connection
import sys

def prompt_nonempty(prompt):
    while True:
        v = input(prompt).strip()
        if v:
            return v
        print("Valor requerido. Intenta de nuevo.")

def main():
    print("=== Crear administrador inicial Ébano ===")
    nombre = prompt_nonempty("Nombre completo: ")
    correo = prompt_nonempty("Correo (ejemplo: admin@ebano.com): ")

    # contraseña (sin eco)
    while True:
        pwd = getpass.getpass("Contraseña (se ocultará): ")
        pwd2 = getpass.getpass("Confirmar contraseña: ")
        if not pwd:
            print("La contraseña no puede quedar vacía.")
            continue
        if pwd != pwd2:
            print("No coinciden. Intenta de nuevo.")
            continue
        break

    # Hashear contraseña con bcrypt
    pwd_bytes = pwd.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

    # Conexión
    conn = get_connection()
    if not conn:
        print("❌ No se pudo conectar a la base de datos. Verifica bd_config.py y .env.")
        sys.exit(1)

    try:
        # Verificar si ya existe un admin con ese correo
        check_q = "SELECT id FROM usuarios WHERE correo = :correo;"
        existing = conn.run(check_q, correo=correo)
        if existing:
            print("⚠️ Ya existe un usuario con ese correo. Abortando.")
            conn.close()
            sys.exit(1)

        telefono = input("Teléfono del admin (opcional): ").strip() or None
        direccion = input("Dirección del admin (opcional): ").strip() or None

        insert_q = """
            INSERT INTO usuarios 
            (nombre_usuario, correo, contraseña, rol, nombre_completo, telefono, direccion)
            VALUES (:nombre_usuario, :correo, :contraseña, :rol, :nombre_completo, :telefono, :direccion)
            RETURNING id;
        """

        nombre_usuario_default = correo.split("@")[0]

        result = conn.run(
            insert_q,
            nombre_usuario=nombre_usuario_default,
            correo=correo,
            contraseña=hashed,
            rol="admin",
            nombre_completo=nombre,
            telefono=telefono,
            direccion=direccion
        )

        # 🔥 Clave: confirmar la transacción antes de cerrar
        conn.commit()

        new_id = result[0][0] if result else None
        conn.close()
        print(f"✅ Administrador creado correctamente. id = {new_id}")

    except Exception as e:
        print("❌ Error al insertar el administrador:", e)
        conn.rollback()  # revierte si algo falla
        conn.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
