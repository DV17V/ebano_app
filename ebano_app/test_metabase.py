#!/usr/bin/env python3
"""
verificar_metabase.py
Script completo para diagnosticar problemas con Metabase en Render

Uso:
    python verificar_metabase.py
"""

import os
import sys
import time
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def print_section(title):
    """Imprime una sección con formato"""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)

def check_env_vars():
    """Verifica las variables de entorno de Metabase"""
    print_section("1. VERIFICACIÓN DE VARIABLES DE ENTORNO")
    
    url = os.getenv("METABASE_PROD_URL", "").strip()
    secret = os.getenv("METABASE_PROD_SECRET_KEY", "").strip()
    
    print(f"\n📝 METABASE_PROD_URL:")
    if url:
        print(f"   ✅ Configurada: {url}")
        if url == "http://localhost:3000":
            print(f"   ⚠️  ADVERTENCIA: Estás usando localhost, debe ser la URL de Render")
        elif not url.startswith("https://"):
            print(f"   ⚠️  ADVERTENCIA: La URL debería usar HTTPS")
    else:
        print(f"   ❌ NO CONFIGURADA")
        return False
    
    print(f"\n🔐 METABASE_PROD_SECRET_KEY:")
    if secret:
        print(f"   ✅ Configurada (longitud: {len(secret)} caracteres)")
        if len(secret) < 32:
            print(f"   ⚠️  ADVERTENCIA: La clave parece muy corta (< 32 caracteres)")
    else:
        print(f"   ❌ NO CONFIGURADA")
        return False
    
    return True

def check_metabase_service(url):
    """Verifica si el servicio de Metabase está en línea"""
    print_section("2. VERIFICACIÓN DEL SERVICIO METABASE")
    
    print(f"\n🌐 Verificando disponibilidad de: {url}")
    
    endpoints_to_check = [
        ("/api/health", "Healthcheck endpoint"),
        ("/api/session/properties", "Session properties"),
        ("/", "Landing page")
    ]
    
    for endpoint, description in endpoints_to_check:
        full_url = f"{url}{endpoint}"
        print(f"\n   Probando: {description}")
        print(f"   URL: {full_url}")
        
        try:
            response = requests.get(full_url, timeout=10)
            print(f"   ✅ Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Servicio respondió correctamente")
                return True
            elif response.status_code == 404:
                print(f"   ⚠️  Endpoint no encontrado (normal en algunos casos)")
            else:
                print(f"   ⚠️  Respuesta inesperada")
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ ERROR: No se pudo conectar al servidor")
            print(f"   💡 El servicio puede estar detenido o la URL es incorrecta")
        except requests.exceptions.Timeout:
            print(f"   ❌ ERROR: Timeout después de 10 segundos")
            print(f"   💡 El servicio puede estar iniciando (Render free tier puede tardar)")
        except Exception as e:
            print(f"   ❌ ERROR: {type(e).__name__}: {str(e)}")
    
    return False

def check_jwt_generation():
    """Verifica que se pueda generar un token JWT"""
    print_section("3. VERIFICACIÓN DE GENERACIÓN DE TOKEN JWT")
    
    try:
        import jwt
        print("\n✅ Librería PyJWT instalada correctamente")
        print(f"   Versión: {jwt.__version__}")
    except ImportError:
        print("\n❌ ERROR: PyJWT no está instalado")
        print("\n💡 SOLUCIÓN: Ejecuta 'pip install PyJWT'")
        return False
    
    secret = os.getenv("METABASE_PROD_SECRET_KEY", "").strip()
    
    if not secret:
        print("\n❌ No se puede generar token sin METABASE_PROD_SECRET_KEY")
        return False
    
    try:
        current_time = round(time.time())
        payload = {
            "resource": {"dashboard": 1},
            "params": {},
            "exp": current_time + 7200,  # 2 horas
            "iat": current_time
        }
        
        token = jwt.encode(payload, secret, algorithm="HS256")
        
        # PyJWT 2.x devuelve string directamente
        if isinstance(token, bytes):
            token = token.decode('utf-8')
        
        print("\n✅ Token JWT generado correctamente")
        print(f"   Longitud del token: {len(token)} caracteres")
        print(f"   Primeros 50 caracteres: {token[:50]}...")
        
        # Verificar que el token se puede decodificar
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        print(f"   ✅ Token decodificado correctamente")
        print(f"   Dashboard ID: {decoded['resource']['dashboard']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR al generar token: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def print_recommendations():
    """Imprime recomendaciones finales"""
    print_section("RECOMENDACIONES Y PRÓXIMOS PASOS")
    
    print("""
📋 CHECKLIST COMPLETO PARA METABASE EN RENDER:

1. ✅ Archivo Dockerfile.metabase correcto:
   - Usar imagen metabase/metabase:v0.48.0 (versión estable)
   - Configurar MB_DB_TYPE=h2 (base de datos embebida)
   - Memoria JVM: -Xmx384m -Xms128m
   - Puerto 3000 expuesto

2. ✅ Configuración en render.yaml:
   - Tipo de servicio: web (docker)
   - Disco persistente: 1GB montado en /metabase-data
   - Health check: /api/health
   - Variables de entorno correctas

3. ✅ En Render Dashboard:
   - Crear servicio "ebano-metabase"
   - Usar Dockerfile.metabase
   - Agregar disco persistente
   - Esperar 5-10 minutos primera vez (puede tardar en iniciar)

4. ✅ Configuración inicial de Metabase:
   - Abrir https://ebano-metabase.onrender.com
   - Crear cuenta de administrador
   - Conectar a base de datos Ébano (PostgreSQL de Render)
   - Crear al menos 1 dashboard
   - Habilitar embedding en Settings → Admin → Embedding
   - Copiar el "Embedding secret key"
   - Agregar a .env como METABASE_PROD_SECRET_KEY

5. ✅ En tu aplicación Flask (.env):
   METABASE_PROD_URL=https://ebano-metabase.onrender.com
   METABASE_PROD_SECRET_KEY=tu_secret_key_aqui

⚠️  LIMITACIONES DEL FREE TIER DE RENDER:
   - El servicio se "duerme" después de 15 minutos sin uso
   - Primera carga puede tomar 30-60 segundos
   - Memoria limitada (512MB) - Metabase es pesado
   - Si tienes problemas persistentes, considera:
     * Usar plan pago de Render ($7/mes)
     * Usar Metabase Cloud (gratis hasta 5 usuarios)
     * Auto-hostear Metabase en otro servicio

🔗 RECURSOS ÚTILES:
   - Docs Metabase: https://www.metabase.com/docs/latest/
   - Embedding en Metabase: https://www.metabase.com/docs/latest/embedding/
   - Render Docs: https://render.com/docs
    """)

def main():
    """Función principal"""
    print("\n" + "🔍 " * 20)
    print("    DIAGNÓSTICO COMPLETO DE METABASE PARA ÉBANO")
    print("🔍 " * 20)
    
    # Paso 1: Verificar variables de entorno
    if not check_env_vars():
        print("\n❌ ERROR CRÍTICO: Variables de entorno no configuradas")
        print("\n💡 Revisa tu archivo .env y agrega:")
        print("   METABASE_PROD_URL=https://ebano-metabase.onrender.com")
        print("   METABASE_PROD_SECRET_KEY=tu_secret_key")
        sys.exit(1)
    
    # Paso 2: Verificar servicio de Metabase
    url = os.getenv("METABASE_PROD_URL", "").strip()
    service_ok = check_metabase_service(url)
    
    if not service_ok:
        print("\n⚠️  ADVERTENCIA: El servicio Metabase no responde")
        print("   Esto puede ser normal si:")
        print("   - Es la primera vez que lo despliegas (tarda 5-10 min)")
        print("   - El servicio está 'dormido' en Render free tier")
        print("   - Hay un error en el Dockerfile")
    
    # Paso 3: Verificar generación de JWT
    jwt_ok = check_jwt_generation()
    
    if not jwt_ok:
        print("\n❌ ERROR: No se puede generar token JWT")
        sys.exit(1)
    
    # Paso 4: Resumen final
    print_section("RESUMEN DEL DIAGNÓSTICO")
    
    print("\n📊 Estado de los componentes:")
    print(f"   Variables de entorno: ✅")
    print(f"   Servicio Metabase: {'✅' if service_ok else '⚠️  (verificar)'}")
    print(f"   Generación JWT: {'✅' if jwt_ok else '❌'}")
    
    if service_ok and jwt_ok:
        print("\n🎉 ¡TODO CONFIGURADO CORRECTAMENTE!")
        print("\n   Puedes acceder al dashboard en:")
        print(f"   {url}")
        print("\n   Y embebido en tu app Flask en:")
        print("   http://localhost:5000/admin/dashboard_analitica")
    else:
        print("\n⚠️  Algunos componentes necesitan atención")
    
    # Paso 5: Recomendaciones
    print_recommendations()

if __name__ == "__main__":
    main()