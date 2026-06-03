import sqlite3
import os

def check_db(db_file):
    if not os.path.exists(db_file):
        return f"Error: {db_file} no existe.\n"
        
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Check if columns exist
    cursor.execute("PRAGMA table_info(entidad);")
    cols = [col[1] for col in cursor.fetchall()]
    
    result = f"Archivo: {db_file} (Tamaño: {os.path.getsize(db_file)} bytes)\n"
    if 'latitude' not in cols or 'longitude' not in cols:
        result += "  -> ERROR: Las columnas de coordenadas NO existen en la tabla entidad.\n\n"
        conn.close()
        return result
        
    cursor.execute("SELECT COUNT(*) FROM entidad;")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM entidad WHERE latitude IS NOT NULL AND longitude IS NOT NULL;")
    geocoded = cursor.fetchone()[0]
    
    result += f"  -> Total de entidades: {total}\n"
    result += f"  -> Entidades con coordenadas: {geocoded} ({geocoded / total * 100:.1f}%)\n"
    
    if geocoded > 0:
        cursor.execute("SELECT nombre, latitude, longitude FROM entidad WHERE latitude IS NOT NULL LIMIT 3;")
        sample = cursor.fetchall()
        result += "  -> Muestra de coordenadas:\n"
        for row in sample:
            result += f"     * {row[0]}: ({row[1]}, {row[2]})\n"
    result += "\n"
    
    conn.close()
    return result

def check():
    output_file = "coords_check.txt"
    
    result = "=== VERIFICACIÓN DE GEOLOCALIZACIÓN DE BASES DE DATOS ===\n\n"
    result += check_db("Recursos_TS_Leon.db")
    result += check_db(os.path.join("data", "Recursos_TS_Leon.db"))
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
        
    print(result)
    print(f"Resultados guardados en {output_file}")

if __name__ == "__main__":
    check()

