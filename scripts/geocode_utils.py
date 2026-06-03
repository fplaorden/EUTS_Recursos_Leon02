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


def clean_address(addr):
    if not isinstance(addr, str) or not addr.strip():
        return ""
    
    # 1. Remove PO Boxes - we should just geocode by zip/city instead of PO box address
    if re.search(r'\b(apdo|apartado|correos|c\.h\.f|chf)\b', addr, flags=re.IGNORECASE):
        return ""

    # 2. Remove parenthetical expressions like "(Edificio C.H.F)", "(entreplanta)", "(Centro de Día)"
    addr = re.sub(r'\(.*?\)', '', addr)
    
    # 3. Remove "s/n" or "S/N" (sin número) so Nominatim can match the street directly
    addr = re.sub(r'\b(s/n|S/N|sin número|sin numero)\b', ' ', addr, flags=re.IGNORECASE)
    
    # 4. Remove floor, door, or section indicators like ", 8º", ", 2º B", "bajo", "Bajo", "1º Izq", "duplicado", "dup"
    addr = re.sub(r',\s*\d+º\s*[a-zA-Z]?', '', addr)
    addr = re.sub(r'\b\d+º\s*[a-zA-Z]?', '', addr)
    addr = re.sub(r',\s*(bajo|Bajo|planta|Planta|izq|Izq|dcha|Dcha|duplicado|dup|DUP)\b', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\b(bajo|Bajo|planta|Planta|izq|Izq|dcha|Dcha|duplicado|dup|DUP)\b', '', addr, flags=re.IGNORECASE)
    
    # 5. Clean common abbreviation variations
    addr = re.sub(r'\bAvda\b\.?', 'Avenida', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bC/\b', 'Calle ', addr)
    addr = re.sub(r'\bCtra\b\.?', 'Carretera', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bNº\s*', '', addr, flags=re.IGNORECASE)
    addr = re.sub(r'\bN\s+(\d+)\b', r'\1', addr, flags=re.IGNORECASE)
    
    # 6. Remove extra commas, periods, and whitespaces
    addr = re.sub(r'\s+', ' ', addr)
    addr = re.sub(r',\s*,', ',', addr)
    addr = re.sub(r'\.\s*\.', '.', addr)
    addr = addr.strip(',. ')
    
    return addr


def get_coordinates(geolocator, address, zip_code, locality, cache, default_coords=(42.598726, -5.568412)):
    """
    Resolve coordinates for an address.
    First checks cache. If not cached, attempts multiple query forms with Nominatim.
    """
    # Clean locality
    loc_clean = str(locality).replace("LEN", "LEÓN").replace("len", "LEÓN").replace("león", "LEÓN").strip()
    loc_clean = re.sub(r'\(.*?\)', '', loc_clean).strip()
    loc_clean = loc_clean.strip('() ')
    
    addr_clean = clean_address(address)
    
    # Create cache key
    cache_key = f"{addr_clean} | {loc_clean} | {zip_code}"
    
    # Check cache
    cached_val = cache.get(cache_key)
    if cached_val:
        return cached_val['lat'], cached_val['lon']
    
    # Limit queries to 2 maximum: street level and locality level
    queries = []
    if addr_clean:
        queries.append(f"{addr_clean}, {loc_clean}, España")
    
    # If the street query fails (or we don't have one), try the locality
    if loc_clean and loc_clean != "nan":
        queries.append(f"{loc_clean}, España")
    elif zip_code and str(zip_code) != "nan":
        try:
            zip_str = f"{int(float(zip_code)):05d}"
            queries.append(f"{zip_str}, España")
        except ValueError:
            pass
    
    location = None
    resolved_query = None
    
    for q in queries:
        try:
            print(f"Geocoding: '{q}'...")
            location = geolocator.geocode(q, timeout=5)
            # Sleep immediately after the web request to stay below rate limit
            time.sleep(1.5)
            if location:
                resolved_query = q
                break
        except Exception as e:
            print(f"Error geocoding query '{q}': {e}")
            time.sleep(1.5)

    if location:
        lat, lon = location.latitude, location.longitude
        print(f"Resolved: '{address}' -> ({lat}, {lon}) via query '{resolved_query}'")
    else:
        lat, lon = default_coords
        print(f"Failed to geocode '{address}'. Using default: ({lat}, {lon})")
        
    # Save to cache
    cache.set(cache_key, {
        'original_address': address,
        'cleaned_address': addr_clean,
        'locality': loc_clean,
        'zip_code': str(zip_code),
        'lat': lat,
        'lon': lon,
        'resolved': location is not None
    })
    
    return lat, lon
