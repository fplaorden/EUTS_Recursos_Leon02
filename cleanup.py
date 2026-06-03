import os
import shutil

# Lista de archivos de depuración y log a eliminar
files_to_delete = [
    "api_8000_debug.txt",
    "api_data_check.txt",
    "api_output_debug.txt",
    "check_api.py",
    "check_api_8000.py",
    "check_api_again.py",
    "check_coords.py",
    "check_ports.py",
    "coords_check.txt",
    "db_schema_output.txt",
    "dump_schema.py",
    "inspect_db.py",
    "ports_check_result.txt",
    "server_log.txt",
    "start_debug.py"
]

def clean():
    print("=== Iniciando Limpieza de Archivos Temporales ===")
    
    # 1. Eliminar archivos de la lista
    for f in files_to_delete:
        if os.path.exists(f):
            try:
                os.remove(f)
                print(f" - Eliminado archivo: {f}")
            except Exception as e:
                print(f" - Error eliminando {f}: {e}")
                
    # 2. Eliminar carpetas __pycache__ de Python
    for root, dirs, files in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                pycache_path = os.path.join(root, d)
                try:
                    shutil.rmtree(pycache_path)
                    print(f" - Eliminada carpeta caché: {pycache_path}")
                except Exception as e:
                    print(f" - Error eliminando caché {pycache_path}: {e}")
                    
    print("\n¡Limpieza completada con éxito!")
    print("Por favor, elimina este script ('cleanup.py') manualmente una vez ejecutado.")

if __name__ == "__main__":
    clean()
