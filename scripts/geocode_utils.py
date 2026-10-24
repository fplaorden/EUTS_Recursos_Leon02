import os
import re
import json
import time
from geopy.geocoders import Nominatim

class GeocodingCache:
    def __init__(self, cache_path):
        self.cache_path = cache_path
        self.cache = {}
        self.load()

    def load(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                print(f"Loaded {len(self.cache)} cached coordinates from {self.cache_path}")
            except Exception as e:
                print(f"Error loading cache: {e}")
                self.cache = {}
        else:
            print("No geocoding cache found. A new one will be created.")

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value
        self.save()


# Metropolitan León bounding box
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

def is_in_leon_metropolitan(lat, lon):
    return (42.540 <= lat <= 42.660) and (-5.660 <= lon <= -5.500)


def clean_address(addr):
    if not isinstance(addr, str) or not addr.strip():
        return ""
    
    # 1. Quitar comillas y textos descriptivos entre comillas
    addr = re.sub(r'["“"”]', '', addr)
    
    # 2. Quitar apartados de correos
    if re.search(r'\b(apdo|apartado|correos|c\.h\.f|chf)\b', addr, flags=re.IGNORECASE):
        return ""

    # 3. Quitar información entre paréntesis
    addr = re.sub(r'\(.*?\)', '', addr)
    
    # 4. Quitar descripciones de edificios o anexos
    addr = re.sub(r'\b(Centro Civico|Centro Cívico|Hospital Princesa Sofia|Campus Universitario|Edificio [^,]+)\b', '', addr, flags=re.IGNORECASE)
    
    # 5. Corregir erratas y nombres oficiales
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
    
    # 6. Manejar números compuestos: "Nº 14 ,16" -> "14", "14-16" -> "14"
    addr = re.sub(r'N[ºo]?\s*(\d+)\s*[,-/]\s*\d+', r'\1', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b(\d+)\s*[,-/]\s*\d+\b', r'\1', addr)
    
    # 7. Quitar plantas, puertas, bajos, entreplantas
    addr = re.sub(r',\s*\d+\s*(planta|bajos?|izq|dcha)?', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b\d+º\s*[a-zA-Z]?', '', addr)
    addr = re.sub(r',\s*(bajo|Bajo|planta|Planta|izq|Izq|dcha|Dcha|entreplanta|Entreplanta)\b.*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b(bajos?|Bajos?|planta|Planta|izqda?|dcha|entreplanta|Entreplanta)\b.*', '', addr, flags=re.IGNORECASE)
    
    # 8. Quitar "s/n" o "sin número"
    addr = re.sub(r'\b(s/n|S/N|sin número|sin numero)\b', '', addr, flags=re.IGNORECASE)
    
    # 9. Quitar "Nº"
    addr = re.sub(r'\bN[ºo]?\s*', '', addr, flags=re.IGNORECASE)
    
    # 10. Quitar esquinas ("esquina Sta. Teresa...")
    addr = re.sub(r'\besquina\s+.*$', '', addr, flags=re.IGNORECASE)
    
    # 11. Limpieza de puntuación sobrante
    addr = re.sub(r'[\.,-]\s*$', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip(' ,.-')
    
    return addr


def get_coordinates(geolocator, address, zip_code, locality, cache, default_coords=DEFAULT_LEON_COORDS):
    """
    Resolve coordinates for an address with strict validation and no false provincial centroids.
    """
    cp_str = str(zip_code).strip() if zip_code else ""
    if cp_str.endswith(".0"):
        cp_str = cp_str[:-2]
    cp_str = cp_str.zfill(5) if len(cp_str) in (4, 5) else cp_str
    
    loc_clean = str(locality or "LEÓN").strip().upper()
    is_leon_city = "LEÓN" in loc_clean or "LEON" in loc_clean or loc_clean in ("", "NONE", "NAN")
    
    addr_clean = clean_address(address)
    
    # Cache key
    cache_key = f"{addr_clean} | {loc_clean} | {cp_str}"
    cached_val = cache.get(cache_key)
    if cached_val:
        lat = cached_val['lat']
        lon = cached_val['lon']
        # Validar que la caché no tenga el centroide erróneo de Quintana del Castillo
        if not (abs(lat - 42.6341451) < 0.001 and abs(lon - (-5.9714151)) < 0.001):
            if not is_leon_city or is_in_leon_metropolitan(lat, lon):
                return lat, lon

    # Si no hay dirección válida
    if not addr_clean:
        if cp_str in POSTAL_CODE_CENTROIDS:
            return POSTAL_CODE_CENTROIDS[cp_str]
        return default_coords

    # Sin prefijo de tipo de vía (para coincidir tanto con Avenida como Calle)
    raw_street = re.sub(r'^(Calle|Avenida|Paseo|Plaza|Carretera)\s+', '', addr_clean, flags=re.IGNORECASE).strip()
    
    queries = []
    if cp_str:
        queries.append((f"{raw_street}, {cp_str} León, España", True))
    queries.append((f"{raw_street}, León, España", True))
    
    if cp_str:
        queries.append((f"{addr_clean}, {cp_str} León, España", True))
    queries.append((f"{addr_clean}, León, España", True))
    
    if addr_clean.startswith("Calle "):
        avda_version = "Avenida " + raw_street
        if cp_str:
            queries.append((f"{avda_version}, {cp_str} León, España", True))
        queries.append((f"{avda_version}, León, España", True))

    location = None
    resolved_query = None

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
                # Verificar que cae dentro de la zona de León
                if is_leon_city:
                    if is_in_leon_metropolitan(lat, lon):
                        location = loc
                        resolved_query = q
                        break
                else:
                    location = loc
                    resolved_query = q
                    break
        except Exception:
            time.sleep(1.0)

    if location:
        lat, lon = location.latitude, location.longitude
        print(f"Resolved: '{address}' -> ({lat}, {lon}) via '{resolved_query}'")
    else:
        # Fallback al centroide del código postal (NO al de la provincia)
        if cp_str in POSTAL_CODE_CENTROIDS:
            lat, lon = POSTAL_CODE_CENTROIDS[cp_str]
            print(f"Fallback CP {cp_str} for '{address}': ({lat}, {lon})")
        else:
            lat, lon = default_coords
            print(f"Fallback default for '{address}': ({lat}, {lon})")

    # Guardar en caché
    cache.set(cache_key, {
        'original_address': address,
        'cleaned_address': addr_clean,
        'locality': loc_clean,
        'zip_code': cp_str,
        'lat': lat,
        'lon': lon,
        'resolved': location is not None
    })

    return lat, lon
