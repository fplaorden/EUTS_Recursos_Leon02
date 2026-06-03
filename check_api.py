import urllib.request
import json
import os

def check():
    url = "http://localhost:8001/api/recursos"
    output_file = "api_data_check.txt"
    
    try:
        req = urllib.request.urlopen(url)
        data = json.loads(req.read().decode('utf-8'))
        
        entities = data.get("entidades", [])
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"Conexión exitosa a {url}\n")
            f.write(f"Total de entidades recibidas por API: {len(entities)}\n\n")
            
            f.write("Primeras 5 entidades recibidas por API:\n")
            for ent in entities[:5]:
                f.write(f" - ID: {ent.get('id')}\n")
                f.write(f"   Nombre: {ent.get('nombre')}\n")
                f.write(f"   Latitude: {ent.get('latitude')} (tipo: {type(ent.get('latitude')).__name__})\n")
                f.write(f"   Longitude: {ent.get('longitude')} (tipo: {type(ent.get('longitude')).__name__})\n")
                f.write(f"   Area: {ent.get('area')}\n")
                f.write(f"   Colectivo: {ent.get('colectivo')}\n\n")
                
        print(f"API checked successfully. Results written to {output_file}")
    except Exception as e:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"ERROR conectando a {url}: {e}\n")
            f.write("¿Está el servidor Flask corriendo en el puerto 8001?\n")
        print(f"API check failed: {e}")

if __name__ == "__main__":
    check()
