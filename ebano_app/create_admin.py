"""
create_admin.py
Script para crear un usuario administrador inicial en la tabla `usuarios`.
Funciona tanto para base de datos local como para producción (Render).

Uso:
- Para BD local: python create_admin.py
- Para BD Render: python create_admin.py --render
"""

import getpass
import bcrypt
import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def get_connection_local():
    """Conexión a base de datos LOCAL (bd_config.py)"""
    from bd_config import get_connection
    return get_connection()

def get_connection_render():
    """Conexión directa a Render usando pg8000 con SSL"""
    import pg8000
    import ssl
    
    # URL de conexión a Render (desde variables de entorno)
    render_url = os.getenv("RENDER_DATABASE_URL")
    
    if not render_url:
        print("❌ ERROR: No se encontró RENDER_DATABASE_URL en el archivo .env")
        print("Agrega esta línea a tu .env:")
        print('RENDER_DATABASE_URL="postgresql://ebano_user:alZ5f9WnQJHzeFyAJQowWONU3W4CwtHI@dpg-d4cb74ili9vc73bte0v0-a.oregon-postgres.render.com/ebano_db"')
        return None
    
    # Parsear URL: postgresql://user:pass@host:port/database
    try:
        # Remover el prefijo postgresql://
        url_without_prefix = render_url.replace("postgresql://", "")
        
        # Separar credenciales y host
        credentials, rest = url_without_prefix.split("@")
        user, password = credentials.split(":")
        
        # Separar host y database
        host_port, database = rest.split("/")
        
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 5432
        
        print(f"🔗 Conectando a Render: {host}/{database}")
        
        # Crear contexto SSL
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Conectar con SSL
        connection = pg8000.connect(
            database=database,
            user=user,
            password=password,
            host=host,
            port=port,
            ssl_context=ssl_context
        )
        
        print("✅ Conexión a Render establecida correctamente.")
        return connection
        
    except Exception as e:
        print(f"❌ Error al conectar a Render: {e}")
        import traceback
        traceback.print_exc()
        return None

def prompt_nonempty(prompt_text):
    """Solicita input no vacío"""
    while True:
        v = input(prompt_text).strip()
        if v:
            return v
        print("⚠️  Valor requerido. Intenta de nuevo.")

def main():
    # Determinar si usar Render o local
    usar_render = "--render" in sys.argv or "-r" in sys.argv
    
    print("=" * 60)
    if usar_render:
        print("🌐 CREAR ADMINISTRADOR EN RENDER (PRODUCCIÓN)")
    else:
        print("💻 CREAR ADMINISTRADOR EN BASE DE DATOS LOCAL")
    print("=" * 60)
    print()
    
    # Solicitar datos del administrador
    nombre = prompt_nonempty("Nombre completo: ")
    correo = prompt_nonempty("Correo (ejemplo: admin@ebano.com): ")

    # Solicitar contraseña (sin eco)
    while True:
        pwd = getpass.getpass("Contraseña (se ocultará): ")
        pwd2 = getpass.getpass("Confirmar contraseña: ")
        if not pwd:
            print("⚠️  La contraseña no puede quedar vacía.")
            continue
        if len(pwd) < 6:
            print("⚠️  La contraseña debe tener al menos 6 caracteres.")
            continue
        if pwd != pwd2:
            print("⚠️  Las contraseñas no coinciden. Intenta de nuevo.")
            continue
        break

    # Datos opcionales
    telefono = input("Teléfono del admin (opcional, Enter para omitir): ").strip() or None
    direccion = input("Dirección del admin (opcional, Enter para omitir): ").strip() or None

    # Hashear contraseña con bcrypt
    print("\n🔐 Generando hash seguro de contraseña...")
    pwd_bytes = pwd.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")
    print("✅ Hash generado correctamente")

    # Conectar a la base de datos
    print()
    if usar_render:
        conn = get_connection_render()
    else:
        conn = get_connection_local()
    
    if not conn:
        print("\n❌ No se pudo conectar a la base de datos.")
        print("\n💡 SOLUCIONES POSIBLES:")
        print("   1. Verifica tu conexión a internet")
        print("   2. Verifica que RENDER_DATABASE_URL esté en .env")
        print("   3. Revisa si tu firewall/antivirus bloquea la conexión")
        print("   4. Intenta desactivar temporalmente VPN si usas una")
        sys.exit(1)

    try:
        # Verificar si ya existe un admin con ese correo
        print(f"\n🔍 Verificando si el correo '{correo}' ya existe...")
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM usuarios WHERE correo = %s;", (correo,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"\n⚠️  Ya existe un usuario con el correo '{correo}'.")
            print("   Abortando creación.")
            cursor.close()
            conn.close()
            sys.exit(1)
        
        print("✅ Correo disponible")

        # Insertar el nuevo administrador
        print(f"\n💾 Creando administrador en la base de datos...")
        insert_q = """
            INSERT INTO usuarios 
            (nombre_usuario, correo, contraseña, rol, nombre_completo, telefono, direccion, pais)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """
        
        nombre_usuario_default = correo.split("@")[0]
        pais = "Colombia"
        
        cursor.execute(
            insert_q,
            (nombre_usuario_default, correo, hashed, "admin", nombre, telefono, direccion, pais)
        )
        
        new_id = cursor.fetchone()[0]
        
        # Confirmar la transacción
        conn.commit()
        cursor.close()
        conn.close()
        
        print()
        print("=" * 60)
        print("✅ ¡ADMINISTRADOR CREADO CORRECTAMENTE!")
        print("=" * 60)
        print(f"   ID: {new_id}")
        print(f"   Usuario: {nombre_usuario_default}")
        print(f"   Correo: {correo}")
        print(f"   Nombre: {nombre}")
        print(f"   Teléfono: {telefono or 'No especificado'}")
        print(f"   Dirección: {direccion or 'No especificada'}")
        if usar_render:
            print(f"   🌐 Base de datos: RENDER (PRODUCCIÓN)")
        else:
            print(f"   💻 Base de datos: LOCAL")
        print("=" * 60)
        print("\n✨ Ya puedes iniciar sesión en tu aplicación con estas credenciales.")

    except Exception as e:
        print(f"\n❌ Error al insertar el administrador: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()