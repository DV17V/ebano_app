"""
refactor_db.py
Script para refactorizar automáticamente el uso de db_connection en app.py
"""

import re
from pathlib import Path

def refactor_app_py():
    app_file = Path('app.py')
    
    if not app_file.exists():
        print("❌ No se encontró app.py")
        return
    
    content = app_file.read_text(encoding='utf-8')
    original_content = content
    
    # Patrón a buscar y reemplazar
    pattern = r'conn = get_connection\(\)\s+(?:if not conn:.*?return.*?\s+)?try:\s+(.*?)finally:\s+try:\s+conn\.close\(\)\s+except:\s+pass'
    
    def replace_pattern(match):
        inner_code = match.group(1)
        
        # Eliminar conn.commit() y conn.rollback() del código interno
        inner_code = re.sub(r'\s*conn\.commit\(\)\s*', '', inner_code)
        inner_code = re.sub(r'\s*try:\s+conn\.rollback\(\)\s+except:\s+pass\s*', '', inner_code)
        inner_code = re.sub(r'\s*conn\.rollback\(\)\s*', '', inner_code)
        
        # Construir el nuevo código con context manager
        return f'with db_connection() as conn:\n{inner_code}'
    
    # Aplicar reemplazo
    new_content = re.sub(pattern, replace_pattern, content, flags=re.DOTALL)
    
    if new_content != original_content:
        # Backup
        backup_file = Path('app.py.backup')
        backup_file.write_text(original_content, encoding='utf-8')
        print(f"✅ Backup creado: {backup_file}")
        
        # Guardar cambios
        app_file.write_text(new_content, encoding='utf-8')
        print(f"✅ app.py refactorizado correctamente")
        print(f"📊 Cambios realizados")
    else:
        print("ℹ️  No se encontraron patrones para refactorizar")

if __name__ == '__main__':
    print("🔧 Iniciando refactorización de app.py...")
    refactor_app_py()
    print("\n✨ Proceso completado")