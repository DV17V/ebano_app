"""
restaurar_datos.py
Migra todos los datos de BD LOCAL a BD RENDER
Sin tocar el esquema de tablas
"""

import os
from dotenv import load_dotenv
import pg8000
import ssl

load_dotenv()

def get_connection_local():
    """Conectar a BD LOCAL"""
    try:
        conn = pg8000.connect(
            database="ebano_db",
            user="postgres",
            password="1234",
            host="localhost",
            port=5432,
            ssl_context=None
        )
        print("✅ Conectado a BD LOCAL")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a LOCAL: {e}")
        return None

def get_connection_render():
    """Conectar a BD RENDER"""
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        conn = pg8000.connect(
            database="ebano_db",
            user="ebano_user",
            password="alZ5f9WnQJHzeFyAJQowWONU3W4CwtHI",
            host="dpg-d4cb74ili9vc73bte0v0-a.oregon-postgres.render.com",
            port=5432,
            ssl_context=ssl_context
        )
        print("✅ Conectado a BD RENDER")
        return conn
    except Exception as e:
        print(f"❌ Error conectando a RENDER: {e}")
        return None

def migrar_datos():
    """Migra datos de LOCAL a RENDER"""
    
    conn_local = get_connection_local()
    conn_render = get_connection_render()
    
    if not conn_local or not conn_render:
        print("❌ No se pudo conectar a una o ambas BDs")
        return False
    
    try:
        cursor_local = conn_local.cursor()
        cursor_render = conn_render.cursor()
        
        print("\n" + "="*60)
        print("🔄 MIGRANDO DATOS LOCAL → RENDER")
        print("="*60)
        
        # ===== 1. USUARIOS =====
        print("\n📋 Migrando USUARIOS...")
        cursor_local.execute("""
            SELECT id, nombre_usuario, correo, contraseña, rol, nombre_completo, 
                   telefono, direccion, estado, pais, fecha_registro
            FROM usuarios;
        """)
        usuarios = cursor_local.fetchall()
        print(f"   Encontrados: {len(usuarios)} usuarios")
        
        for u in usuarios:
            try:
                cursor_render.execute("""
                    INSERT INTO usuarios 
                    (id, nombre_usuario, correo, contraseña, rol, nombre_completo, 
                     telefono, direccion, estado, pais, fecha_registro)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, u)
            except Exception as e:
                print(f"   ⚠️  Error insertando usuario {u[1]}: {e}")
        conn_render.commit()
        print(f"   ✅ Usuarios migrados")
        
        # ===== 2. PRODUCTOS =====
        print("\n📦 Migrando PRODUCTOS...")
        cursor_local.execute("""
            SELECT id, nombre, descripcion, precio, stock, imagen_url, fecha_creacion
            FROM productos;
        """)
        productos = cursor_local.fetchall()
        print(f"   Encontrados: {len(productos)} productos")
        
        for p in productos:
            try:
                cursor_render.execute("""
                    INSERT INTO productos 
                    (id, nombre, descripcion, precio, stock, imagen_url, fecha_creacion)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, p)
            except Exception as e:
                print(f"   ⚠️  Error insertando producto {p[1]}: {e}")
        conn_render.commit()
        print(f"   ✅ Productos migrados")
        
        # ===== 3. PEDIDOS =====
        print("\n🛒 Migrando PEDIDOS...")
        cursor_local.execute("""
            SELECT id, id_usuario, fecha_pedido, estado, total
            FROM pedidos;
        """)
        pedidos = cursor_local.fetchall()
        print(f"   Encontrados: {len(pedidos)} pedidos")
        
        for ped in pedidos:
            try:
                cursor_render.execute("""
                    INSERT INTO pedidos 
                    (id, id_usuario, fecha_pedido, estado, total)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, ped)
            except Exception as e:
                print(f"   ⚠️  Error insertando pedido {ped[0]}: {e}")
        conn_render.commit()
        print(f"   ✅ Pedidos migrados")
        
        # ===== 4. DETALLE PEDIDOS =====
        print("\n📝 Migrando DETALLE PEDIDOS...")
        cursor_local.execute("""
            SELECT id, id_pedido, id_producto, cantidad, subtotal
            FROM detalle_pedidos;
        """)
        detalles = cursor_local.fetchall()
        print(f"   Encontrados: {len(detalles)} detalles")
        
        for det in detalles:
            try:
                cursor_render.execute("""
                    INSERT INTO detalle_pedidos 
                    (id, id_pedido, id_producto, cantidad, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, det)
            except Exception as e:
                print(f"   ⚠️  Error insertando detalle {det[0]}: {e}")
        conn_render.commit()
        print(f"   ✅ Detalles migrados")
        
        # ===== 5. RESEÑAS =====
        print("\n⭐ Migrando RESEÑAS...")
        cursor_local.execute("""
            SELECT id, id_usuario, id_producto, comentario, calificacion, fecha
            FROM resenas;
        """)
        resenas = cursor_local.fetchall()
        print(f"   Encontrados: {len(resenas)} reseñas")
        
        for r in resenas:
            try:
                cursor_render.execute("""
                    INSERT INTO resenas 
                    (id, id_usuario, id_producto, comentario, calificacion, fecha)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING;
                """, r)
            except Exception as e:
                print(f"   ⚠️  Error insertando reseña {r[0]}: {e}")
        conn_render.commit()
        print(f"   ✅ Reseñas migradas")
        
        print("\n" + "="*60)
        print("✅ MIGRACIÓN COMPLETADA EXITOSAMENTE")
        print("="*60)
        print(f"\n📊 RESUMEN:")
        print(f"   • Usuarios: {len(usuarios)}")
        print(f"   • Productos: {len(productos)}")
        print(f"   • Pedidos: {len(pedidos)}")
        print(f"   • Detalles: {len(detalles)}")
        print(f"   • Reseñas: {len(resenas)}")
        print(f"\n✨ Los datos de LOCAL están ahora en RENDER")
        
        cursor_local.close()
        cursor_render.close()
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR durante migración: {e}")
        import traceback
        traceback.print_exc()
        try:
            conn_render.rollback()
        except:
            pass
        return False
    finally:
        try:
            conn_local.close()
        except:
            pass
        try:
            conn_render.close()
        except:
            pass

if __name__ == "__main__":
    print("\n⚠️  ADVERTENCIA:")
    print("   Esta operación copiará TODOS los datos de LOCAL a RENDER")
    print("   Los datos existentes en RENDER se sobrescribirán")
    
    confirmacion = input("\n¿Continuar? (escribir 'SI' para confirmar): ").strip().upper()
    
    if confirmacion == "SI":
        print()
        migrar_datos()
    else:
        print("❌ Operación cancelada")