import os
import sys
import sqlite3
import json
import time
from geopy.geocoders import Nominatim

# Add current scripts directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)
from robust_geocoding import (
    resolve_entity_coordinates, 
    is_in_leon_metropolitan, 
    clean_address, 
    POSTAL_CODE_CENTROIDS, 
    DEFAULT_LEON_COORDS
)

WORKSPACE_DIR = os.path.dirname(SCRIPT_DIR)
DB_ROOT = os.path.join(WORKSPACE_DIR, "Recursos_TS_Leon.db")
DB_DATA = os.path.join(WORKSPACE_DIR, "data", "Recursos_TS_Leon.db")
CACHE_FILE = os.path.join(WORKSPACE_DIR, "data", "geocoding_cache.json")

def needs_fix(lat, lon, localidad):
    if lat is None or lon is None:
        return True
    
    # Quintana del Castillo provincial centroid error (exact or close)
    if abs(lat - 42.6341451) < 0.001 and abs(lon - (-5.9714151)) < 0.001:
        return True
        
    # Outside Spain
    if not (36.0 <= lat <= 44.0 and -10.0 <= lon <= 4.0):
        return True
        
    loc = (localidad or "").strip().upper()
    is_leon = "LEÓN" in loc or "LEON" in loc
    
    # In León city but coordinates placed it outside metropolitan León
    if is_leon and not is_in_leon_metropolitan(lat, lon):
        return True
        
    return False

def run_fix():
    print("=== Iniciando corrección de geolocalización para todos los recursos ===")
    
    # Load or init cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    geolocator = Nominatim(user_agent="euts_leon_mass_geoloc_fixer_2026")
    
    # Connect to primary DB
    conn = sqlite3.connect(DB_ROOT)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT id_entidad, nombre, direccion, cp, localidad, latitude, longitude FROM entidad")
    all_rows = c.fetchall()
    
    to_fix = []
    for r in all_rows:
        lat = r['latitude']
        lon = r['longitude']
        loc = r['localidad']
        if needs_fix(lat, lon, loc):
            to_fix.append(r)
            
    print(f"Total entidades en la base de datos: {len(all_rows)}")
    print(f"Entidades con coordenadas erróneas o pendientes: {len(to_fix)}")
    
    fixed_count = 0
    updated_records = []
    
    for idx, r in enumerate(to_fix, 1):
        ent_id = r['id_entidad']
        name = r['nombre']
        addr = r['direccion']
        cp = r['cp']
        loc_name = r['localidad']
        old_lat = r['latitude']
        old_lon = r['longitude']
        
        print(f"\n[{idx}/{len(to_fix)}] ID {ent_id}: {name}")
        print(f"   Dirección: {addr} | CP: {cp} | Localidad: {loc_name}")
        print(f"   Coordenadas anteriores: ({old_lat}, {old_lon})")
        
        coords, method = resolve_entity_coordinates(geolocator, name, addr, cp, loc_name)
        new_lat, new_lon = coords
        print(f"   => NUEVAS COORDENADAS: ({new_lat:.6f}, {new_lon:.6f}) vía [{method}]")
        
        # Save to DB
        c.execute("UPDATE entidad SET latitude = ?, longitude = ? WHERE id_entidad = ?", (new_lat, new_lon, ent_id))
        conn.commit()
        
        # Cache
        cache_key = f"{clean_address(addr)} | {loc_name} | {cp}"
        cache[cache_key] = {
            'lat': new_lat,
            'lon': new_lon,
            'nombre': name,
            'direccion': addr,
            'metodo': method,
            'timestamp': time.time()
        }
        
        updated_records.append((ent_id, new_lat, new_lon))
        fixed_count += 1
        
    conn.close()
    
    # Save cache
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
        
    # Also update data/Recursos_TS_Leon.db if it exists
    if os.path.exists(DB_DATA):
        print("\nSincronizando base de datos en data/Recursos_TS_Leon.db...")
        conn_data = sqlite3.connect(DB_DATA)
        c_data = conn_data.cursor()
        for ent_id, lat, lon in updated_records:
            c_data.execute("UPDATE entidad SET latitude = ?, longitude = ? WHERE id_entidad = ?", (lat, lon, ent_id))
        conn_data.commit()
        conn_data.close()
        print("Sincronización completada.")
        
    print(f"\n=== PROCESO COMPLETADO ===")
    print(f"Total entidades corregidas: {fixed_count}")

if __name__ == "__main__":
    run_fix()
