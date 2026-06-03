import urllib.request
import json

ports = [8000, 8001]
results = []

for port in ports:
    url = f"http://localhost:{port}/api/recursos"
    try:
        req = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=2)
        data = json.loads(req.read().decode('utf-8'))
        results.append(f"Puerto {port}: ACTIVO. Encontradas {len(data.get('entidades', []))} entidades.")
    except Exception as e:
        results.append(f"Puerto {port}: INACTIVO. Error: {e}")

with open("ports_check_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(results))
    
print("Puertos comprobados. Resultados en ports_check_result.txt")
