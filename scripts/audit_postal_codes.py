import sqlite3

for db_path in ['Recursos_TS_Leon.db', 'data/Recursos_TS_Leon.db']:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT id_entidad, nombre, direccion, cp, localidad, latitude, longitude FROM entidad')
    rows = c.fetchall()
    print(f"=== DB: {db_path} ({len(rows)} entities) ===")
    
    # 1. Non-24 postal codes
    non_24 = [r for r in rows if r['cp'] and not str(r['cp']).strip().startswith('24')]
    print(f"Non-24 postal codes: {len(non_24)}")
    for r in non_24:
        print(f"  ID {r['id_entidad']}: {r['nombre']} | {r['direccion']} | CP: {r['cp']} | Loc: {r['localidad']} | Coords: ({r['latitude']}, {r['longitude']})")

    # 2. Coordinates outside León province
    # Bounding box of León Province:
    # Latitude: 42.0 to 43.3
    # Longitude: -7.1 to -4.8
    outside_leon_prov = []
    for r in rows:
        lat, lon = r['latitude'], r['longitude']
        if lat is None or lon is None:
            outside_leon_prov.append((r, "NULL_COORDS"))
        elif not (42.0 <= lat <= 43.3 and -7.1 <= lon <= -4.8):
            outside_leon_prov.append((r, f"COORDS_OUTSIDE_LEON_PROVINCE: ({lat}, {lon})"))
            
    print(f"\nEntities with coordinates outside León province: {len(outside_leon_prov)}")
    for r, reason in outside_leon_prov:
        print(f"  ID {r['id_entidad']}: {r['nombre']} | {r['direccion']} | CP: {r['cp']} | Loc: {r['localidad']} | {reason}")

    # 3. CP distribution
    cp_counts = {}
    for r in rows:
        cp = str(r['cp']).strip() if r['cp'] else "SIN_CP"
        cp_counts[cp] = cp_counts.get(cp, 0) + 1
        
    print("\nPostal Code distribution:")
    for cp, cnt in sorted(cp_counts.items(), key=lambda x: -x[1]):
        print(f"  CP {cp:8s}: {cnt:3d} entidades")
