import os
import re
import sqlite3
import time
from geopy.geocoders import Nominatim

# Bounding box for Metropolitan León (León capital, San Andrés, Villaquilambre)
LEON_VIEWBOX = [(42.65, -5.65), (42.54, -5.50)]

# Postal code approximate centroids within León to avoid generic provincial centroids
POSTAL_CODE_CENTROIDS = {
    '24001': (42.5983, -5.5745),  # Centro, Santo Domingo, Guzmán, Ordoño II
    '24002': (42.6022, -5.5725),  # Centro, San Isidoro, Ramón y Cajal
    '24003': (42.5975, -5.5665),  # Casco Antiguo, Catedral, Plaza Mayor, Santa Nonia
    '24004': (42.5925, -5.5740),  # Chantría, San Claudio, Fernández Ladreda
    '24005': (42.5920, -5.5650),  # El Ejido, Santa Ana, José Aguado, Alcalde Miguel Castaño
    '24006': (42.5850, -5.5620),  # La Lastra, Moisés de León
    '24007': (42.6080, -5.5620),  # La Palomera, San Mamés, Campus Universitario
    '24008': (42.6130, -5.5710),  # Mariano Andrés, Cantamilanos, Hospital
    '24009': (42.5960, -5.5920),  # El Crucero, Armunia, Oteruelo, Magdalena
    '24010': (42.6070, -5.6020),  # Trobajo del Camino, San Andrés del Rabanedo
    '24191': (42.6150, -5.6150),  # San Andrés del Rabanedo
    '24193': (42.6220, -5.5550),  # Villaquilambre / Navatejera
    '24195': (42.6110, -5.5510),  # Villaobispo de las Regueras
    '24198': (42.5780, -5.6480),  # La Virgen del Camino
    '24227': (42.5750, -5.5150),  # Valdelafuente
    '47001': (41.6523, -4.7245),  # Valladolid centro (Junta)
}

DEFAULT_LEON_COORDS = (42.598726, -5.568412) # Plaza de Santo Domingo, León

def clean_address(addr):
    if not addr or not isinstance(addr, str):
        return ""
    
    # Quitar citas y comillas
    addr = re.sub(r'["“"”]', '', addr)
    
    # Quitar información entre paréntesis
    addr = re.sub(r'\(.*?\)', '', addr)
    
    # Quitar descripciones de edificios o anexos
    addr = re.sub(r'\b(Centro Civico|Centro Cívico|Hospital Princesa Sofia|Campus Universitario|Edificio [^,]+)\b', '', addr, flags=re.IGNORECASE)
    
    # Corregir nombres y erratas conocidas
    addr = re.sub(r'\bAcalde\b', 'Alcalde', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bSan Júan\b', 'San Juan', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bMadalena\b', 'Magdalena', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bAlferez\b', 'Alférez', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bD\.\s*Gutierre\b', 'Don Gutierre', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bMarqu[eé]s de San Isidro\b', 'Marqueses de San Isidro', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bJos[eé] M[aª]\s*', 'José María ', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bPza\.?\b', 'Plaza', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bPº\b', 'Paseo', addr)
    addr = re.sub(r'\bCtra\.?\b', 'Carretera', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bC/\b', 'Calle ', addr)
    addr = re.sub(r'\bAvda\.?\b', 'Avenida', addr, flags=re.IGNORECASE)
    
    # Manejar números compuestos: "Nº 14 ,16" -> "14", "14-16" -> "14"
    addr = re.sub(r'N[ºo]?\s*(\d+)\s*[,-/]\s*\d+', r'\1', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b(\d+)\s*[,-/]\s*\d+\b', r'\1', addr)
    
    # Quitar plantas, puertas, bajos, entreplantas
    addr = re.sub(r',\s*\d+\s*(planta|bajos?|izq|dcha)?', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b\d+º\s*[a-zA-Z]?', '', addr)
    addr = re.sub(r',\s*(bajo|Bajo|planta|Planta|izq|Izq|dcha|Dcha|entreplanta|Entreplanta)\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b(bajos?|Bajos?|planta|Planta|izqda?|dcha|entreplanta|Entreplanta)\b.*', '', addr, flags=re.IGNORECASE)
    
    # Quitar "s/n" o "sin número"
    addr = re.sub(r'\b(s/n|S/N|sin número|sin numero)\b', '', addr, flags=re.IGNORECASE)
    
    # Quitar "Nº"
    addr = re.sub(r'\bN[ºo]?\s*', '', addr, flags=re.IGNORECASE)
    
    # Quitar esquinas ("esquina Sta. Teresa...")
    addr = re.sub(r'\besquina\s+.*$', '', addr, flags=re.IGNORECASE)
    
    # Limpieza final de espacios y signos
    addr = re.sub(r'[\.,-]\s*$', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip(' ,.-')
    
    return addr

def is_in_leon_metropolitan(lat, lon):
    return (42.540 <= lat <= 42.660) and (-5.660 <= lon <= -5.500)

def resolve_entity_coordinates(geolocator, nombre, direccion, cp, localidad):
    cp_str = str(cp).strip() if cp else ""
    if cp_str.endswith(".0"):
        cp_str = cp_str[:-2]
    cp_str = cp_str.zfill(5) if len(cp_str) in (4, 5) else cp_str
    
    loc_clean = str(localidad or "LEÓN").strip().upper()
    is_leon_city = "LEÓN" in loc_clean or "LEON" in loc_clean or loc_clean in ("", "NONE", "NAN")
    
    addr_clean = clean_address(direccion)
    
    # Si no hay dirección
    if not addr_clean:
        if cp_str in POSTAL_CODE_CENTROIDS:
            return POSTAL_CODE_CENTROIDS[cp_str], "CP_FALLBACK_NO_ADDR"
        if is_leon_city:
            return DEFAULT_LEON_COORDS, "DEFAULT_LEON_NO_ADDR"
        return DEFAULT_LEON_COORDS, "DEFAULT_NO_ADDR"

    # Preparar variaciones de la calle:
    # 1. Sin prefijo tipo de vía ("Ramón y Cajal 14")
    raw_street = re.sub(r'^(Calle|Avenida|Paseo|Plaza|Carretera)\s+', '', addr_clean, flags=re.IGNORECASE).strip()
    
    queries = []
    
    # Intentar con nombre específico de la entidad si es muy conocido
    if any(k in nombre.lower() for k in ['hospital', 'colegio', 'escuela infantil', 'biblioteca pública', 'centro de salud', 'cruz roja']):
        queries.append((f"{nombre}, León, España", True))
        
    # Formas de búsqueda:
    # A) Sin prefijo de vía (permite a OSM encontrar tanto Avenida como Calle)
    if cp_str:
        queries.append((f"{raw_street}, {cp_str} León, España", True))
    queries.append((f"{raw_street}, León, España", True))
    
    # B) Con dirección limpia completa
    if cp_str:
        queries.append((f"{addr_clean}, {cp_str} León, España", True))
    queries.append((f"{addr_clean}, León, España", True))
    
    # C) Si empezaba por Calle, probar también con Avenida
    if addr_clean.startswith("Calle "):
        avda_version = "Avenida " + raw_street
        if cp_str:
            queries.append((f"{avda_version}, {cp_str} León, España", True))
        queries.append((f"{avda_version}, León, España", True))

    # Ejecutar consultas con bounded en León
    for q, use_viewbox in queries:
        try:
            kwargs = {
                'country_codes': 'es',
                'addressdetails': True
            }
            if use_viewbox and is_leon_city:
                kwargs['viewbox'] = LEON_VIEWBOX
                kwargs['bounded'] = True
                
            loc = geolocator.geocode(q, **kwargs)
            time.sleep(1.0)
            if loc:
                lat, lon = loc.latitude, loc.longitude
                if is_leon_city:
                    if is_in_leon_metropolitan(lat, lon):
                        return (lat, lon), f"GEOCODED: {q}"
                else:
                    # Fuera de León ciudad (ej. Valladolid u otro pueblo)
                    return (lat, lon), f"GEOCODED_OTHER: {q}"
        except Exception as e:
            time.sleep(1.0)

    # Si la búsqueda por calle falló pero sabemos el código postal
    if cp_str in POSTAL_CODE_CENTROIDS:
        return POSTAL_CODE_CENTROIDS[cp_str], f"CP_FALLBACK: {cp_str}"
        
    if is_leon_city:
        return DEFAULT_LEON_COORDS, "DEFAULT_LEON_FALLBACK"
        
    return DEFAULT_LEON_COORDS, "DEFAULT_FALLBACK"
