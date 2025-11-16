"""
test_metabase.py
Ejecuta esto para saber qué está fallando con Metabase
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("\n" + "="*60)
print("DIAGNÓSTICO DE METABASE")
print("="*60)

# 1. Verificar variables de entorno
url = os.getenv("METABASE_PROD_URL")
secret = os.getenv("METABASE_PROD_SECRET_KEY")

print(f"\n1. METABASE_PROD_URL: {url}")
print(f"2. METABASE_PROD_SECRET_KEY: {'Configurada ✓' if secret else 'NO CONFIGURADA ✗'}")

if not url:
    print("\n❌ PROBLEMA: METABASE_PROD_URL no está en .env")
    print("\nSOLUCIÓN: Agrega esta línea a tu .env:")
    print("METABASE_PROD_URL=https://ebano-metabase.onrender.com")
    
if not secret:
    print("\n❌ PROBLEMA: METABASE_PROD_SECRET_KEY no está en .env")
    print("\nSOLUCIÓN: Necesitas obtenerla de Metabase:")
    print("1. Abre https://ebano-metabase.onrender.com")
    print("2. Ve a Settings → Admin → Embedding")
    print("3. Copia el 'Embedding secret key'")
    print("4. Agrégalo a .env como METABASE_PROD_SECRET_KEY=...")

if url and secret:
    print("\n✅ Variables configuradas correctamente")
    print(f"\nPrueba abrir esto en tu navegador:")
    print(url)

print("\n" + "="*60)