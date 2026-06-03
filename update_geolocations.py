import os
import sqlite3
import time
import sys

def main():
    db_file = "Recursos_TS_Leon.db"
    cache_file = "geocoding_cache.json"
    
    if not os.path.exists(db_file):
        print(f"Error: {db_file} no encontrado en la raíz del proyecto.")
        return
        
    print("Conectando a la base de datos...")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # 1. Asegurar que existen las columnas en la tabla entidad
    cursor.execute("PRAGMA table_info(entidad);")
    cols = [col[1] for col in cursor.fetchall()]
    if 'latitude' not in cols:
        cursor.execute("ALTER TABLE entidad ADD COLUMN latitude REAL;")
        print("Columna 'latitude' agregada a la tabla entidad.")
    if 'longitude' not in cols:
        cursor.execute("ALTER TABLE entidad ADD COLUMN longitude REAL;")
        print("Columna 'longitude' agregada a la tabla entidad.")
    conn.commit()

    # 2. Buscar entidades que no tengan coordenadas
    cursor.execute("SELECT id_entidad, nombre, direccion, cp, localidad FROM entidad WHERE latitude IS NULL OR longitude IS NULL")
    entities = cursor.fetchall()
    
    if not entities:
        print("Todas las entidades ya tienen coordenadas. ¡No hay nada que geolocalizar!")
        conn.close()
        return

    print(f"Se encontraron {len(entities)} entidades sin geolocalización.")
    print("Inicializando geocodificador Nominatim...")
    
    # Agregar ruta al path para importar geocode_utils
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))
    try:
        from geocode_utils import GeocodingCache, get_coordinates
        from geopy.geocoders import Nominatim
    except ImportError as e:
        print(f"Error de importación: {e}")
        print("Por favor, asegúrate de haber instalado los requerimientos usando: pip install -r requirements.txt")
        conn.close()
        return
        
    geolocator = Nominatim(user_agent="león_social_resources_app_updater")
    cache = GeocodingCache(cache_file)
    
    success_count = 0
    fail_count = 0
    
    for idx, (ent_id, nombre, direccion, cp, localidad) in enumerate(entities, 1):
        localidad = localidad or "LEÓN"
        print(f"[{idx}/{len(entities)}] Geolocalizando '{nombre}'...")
        
        if not direccion:
            print(f"  -> Omitido: Sin dirección válida.")
            fail_count += 1
            continue
            
        try:
            # Obtener coordenadas usando el resolvedor con caché
            lat, lon = get_coordinates(geolocator, direccion, cp, localidad, cache)
            
            # Guardar en la base de datos
            cursor.execute("UPDATE entidad SET latitude = ?, longitude = ? WHERE id_entidad = ?", (lat, lon, ent_id))
            conn.commit()
            success_count += 1
            print(f"  -> Resoluto: ({lat}, {lon})")
        except Exception as e:
            fail_count += 1
            print(f"  -> Error: {e}")
            
    conn.close()
    print("\n=== Proceso de Geolocalización Terminado ===")
    print(f"Entidades actualizadas con éxito: {success_count}")
    print(f"Entidades con errores o sin dirección: {fail_count}")

if __name__ == "__main__":
    main()
