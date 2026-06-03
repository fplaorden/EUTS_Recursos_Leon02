import os
import sqlite3
import secrets
import threading
import sys
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Config security
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "euts_leon_assistance_social_secure_key_2026_xYz987!")
app.permanent_session_lifetime = timedelta(hours=2)

# Enable cookie security flags
# Enforce HttpOnly and SameSite. Secure is enabled when not in debug mode
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=not app.debug
)

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(WORKSPACE_DIR, "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "Recursos_TS_Leon.db")
CACHE_PATH = os.path.join(DB_DIR, "geocoding_cache.json")
LOG_PATH = os.path.join(DB_DIR, "sent_emails.log")

# Bootstrap database from root if needed (important for Docker persistent volumes)
root_db = os.path.join(WORKSPACE_DIR, "Recursos_TS_Leon.db")

def should_bootstrap():
    if not os.path.exists(DB_PATH):
        return True
    
    # Check if active DB lacks coordinates but root DB has them
    try:
        conn_active = sqlite3.connect(DB_PATH)
        c_active = conn_active.cursor()
        c_active.execute("PRAGMA table_info(entidad);")
        active_cols = [col[1] for col in c_active.fetchall()]
        
        active_coords = 0
        if 'latitude' in active_cols and 'longitude' in active_cols:
            c_active.execute("SELECT COUNT(*) FROM entidad WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
            active_coords = c_active.fetchone()[0]
        conn_active.close()
        
        if active_coords == 0 and os.path.exists(root_db):
            conn_root = sqlite3.connect(root_db)
            c_root = conn_root.cursor()
            c_root.execute("PRAGMA table_info(entidad);")
            root_cols = [col[1] for col in c_root.fetchall()]
            if 'latitude' in root_cols and 'longitude' in root_cols:
                c_root.execute("SELECT COUNT(*) FROM entidad WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
                root_coords = c_root.fetchone()[0]
                conn_root.close()
                if root_coords > 0:
                    print(f"Active DB has 0 geocoded entities, but root DB has {root_coords}. Bootstrapping root DB...")
                    return True
            else:
                conn_root.close()
    except Exception as e:
        print(f"Error checking coordinates during bootstrap check: {e}")
        return True
    return False

if should_bootstrap():
    if os.path.exists(root_db):
        import shutil
        try:
            # If the database file is locked or open, try closing any handles or catching the error
            if os.path.exists(DB_PATH):
                try:
                    os.remove(DB_PATH)
                except Exception:
                    # If we can't remove (file locked), try copying over it directly
                    pass
            shutil.copy2(root_db, DB_PATH)
            print(f"Bootstrapped database from root to: {DB_PATH}")
        except Exception as e:
            print(f"Error bootstrapping database: {e}")
    else:
        print(f"Warning: No database found at {root_db} or {DB_PATH}")



def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Migrate the database, creating required tables and columns if missing"""
    print(f"Initializing database at {DB_PATH}...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Password Recovery Tokens Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recovery_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at DATETIME NOT NULL,
        used BOOLEAN DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)
    
    # 3. Add Geolocation columns to entidad table if not exist
    cursor.execute("PRAGMA table_info(entidad);")
    cols = [col[1] for col in cursor.fetchall()]
    if 'latitude' not in cols:
        cursor.execute("ALTER TABLE entidad ADD COLUMN latitude REAL;")
        print("Added 'latitude' column to 'entidad' table.")
    if 'longitude' not in cols:
        cursor.execute("ALTER TABLE entidad ADD COLUMN longitude REAL;")
        print("Added 'longitude' column to 'entidad' table.")
        
    # 4. Insert default admin user if no users exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        default_user = "admin"
        default_email = "admin@leon.es"
        # Highly secure PBKDF2 hash
        default_pass_hash = generate_password_hash("admin_password_change_me", method="pbkdf2:sha256:600000")
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (default_user, default_email, default_pass_hash)
        )
        print(f"Default admin user created. Username: {default_user}, Email: {default_email}")
        
    conn.commit()
    conn.close()

# Initialize DB structure on startup
init_database()


# Background Geocoding Thread
def run_background_geocoding():
    print("Background geocoding thread starting...")
    try:
        # Check if we need to resolve coordinates
        conn = get_db_connection()
        rows = conn.execute("SELECT id_entidad, direccion, cp, localidad FROM entidad WHERE latitude IS NULL OR longitude IS NULL").fetchall()
        conn.close()
        
        if not rows:
            print("All entities already geocoded.")
            return
            
        print(f"Found {len(rows)} entities without coordinates. Initializing geocoder...")
        from scripts.geocode_utils import GeocodingCache, get_coordinates
        from geopy.geocoders import Nominatim
        
        geolocator = Nominatim(user_agent="león_social_resources_app_v2")
        cache = GeocodingCache(CACHE_PATH)
        
        for row in rows:
            ent_id = row['id_entidad']
            addr = row['direccion']
            cp = row['cp']
            localidad = row['localidad'] or "LEÓN"
            
            if not addr:
                continue
                
            lat, lon = get_coordinates(geolocator, addr, cp, localidad, cache)
            
            # Save coordinates
            conn = get_db_connection()
            conn.execute("UPDATE entidad SET latitude = ?, longitude = ? WHERE id_entidad = ?", (lat, lon, ent_id))
            conn.commit()
            conn.close()
            
        print("Background geocoding finished successfully.")
    except Exception as e:
        print(f"Error during background geocoding: {e}")

# Start geocoding thread
threading.Thread(target=run_background_geocoding, daemon=True).start()


def login_required(f):
    """Decorator to require login on API routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "No autorizado. Inicie sesión primero."}), 401
        return f(*args, **kwargs)
    return decorated_function


# --- EMAIL RECOVERY UTILITY ---
def send_recovery_email(email, reset_link, username):
    smtp_server = os.environ.get("SMTP_SERVER", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    smtp_from = os.environ.get("SMTP_FROM", "noreply@leon.es")

    subject = "Recuperación de contraseña - Asistencia Social León"
    body = f"""Hola, {username}.

Has solicitado restablecer tu contraseña en el portal de Recursos de Asistencia Social de León.

Para restablecer tu contraseña, haz clic en el siguiente enlace o cópialo en tu navegador:
{reset_link}

Este enlace expirará en 1 hora. Si no has solicitado esto, puedes ignorar este correo.

Saludos,
Ayuntamiento de León
"""

    if smtp_server:
        # Send actual email
        try:
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = smtp_from
            msg['To'] = email

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [email], msg.as_string())
            print(f"Sent recovery email to {email}")
            return True
        except Exception as e:
            print(f"Failed to send SMTP email: {e}")
            # Fall back to logging
    
    # Logging fallback
    try:
        log_entry = f"""========================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
To: {email}
Subject: {subject}
Reset Link: {reset_link}
Content:
{body}
========================================
"""
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"Logged recovery email to {LOG_PATH}")
        return True
    except Exception as e:
        print(f"Failed to write email to log: {e}")
        return False


# --- AUTHENTICATION ROUTES ---
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    username_or_email = data.get('username')
    password = data.get('password')
    
    if not username_or_email or not password:
        return jsonify({"error": "Faltan credenciales"}), 400
        
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?", 
        (username_or_email, username_or_email)
    ).fetchone()
    conn.close()
    
    if user and check_password_hash(user['password_hash'], password):
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['email'] = user['email']
        return jsonify({
            "message": "Login exitoso",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "email": user['email']
            }
        })
        
    return jsonify({"error": "Credenciales inválidas"}), 401


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Sesión cerrada correctamente"})


@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            "authenticated": True,
            "user": {
                "id": session['user_id'],
                "username": session['username'],
                "email": session['email']
            }
        })
    return jsonify({"authenticated": False}), 200


@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.json or {}
    email = data.get('email')
    
    if not email:
        return jsonify({"error": "Se requiere el correo electrónico"}), 400
        
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    
    # Generate token always to prevent timing attacks, but save only if user exists
    token = secrets.token_hex(32)
    expires = datetime.now() + timedelta(hours=1)
    
    if user:
        conn.execute(
            "INSERT INTO recovery_tokens (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user['id'], token, expires.strftime('%Y-%m-%d %H:%M:%S'))
        )
        conn.commit()
        
        # Build reset link. Nginx config maps this.
        host = request.headers.get('Host', 'localhost:8001')
        proto = "https" if request.headers.get('X-Forwarded-Proto') == 'https' else "http"
        reset_link = f"{proto}://{host}/login.html?token={token}"
        
        send_recovery_email(email, reset_link, user['username'])
        
    conn.close()
    return jsonify({"message": "Si el correo está registrado, se enviará un enlace de recuperación."})


@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    token = data.get('token')
    new_password = data.get('password')
    
    if not token or not new_password:
        return jsonify({"error": "Token y contraseña requeridos"}), 400
        
    conn = get_db_connection()
    
    # Find token
    token_row = conn.execute(
        "SELECT * FROM recovery_tokens WHERE token = ? AND used = 0 AND expires_at > ?",
        (token, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    ).fetchone()
    
    if not token_row:
        conn.close()
        return jsonify({"error": "Token inválido o expirado"}), 400
        
    # Hash and update
    hashed = generate_password_hash(new_password, method="pbkdf2:sha256:600000")
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, token_row['user_id']))
    conn.execute("UPDATE recovery_tokens SET used = 1 WHERE id = ?", (token_row['id'],))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Contraseña restablecida correctamente."})


# --- RESOURCE API ROUTES ---
@app.route('/api/recursos', methods=['GET'])
def get_recursos():
    conn = get_db_connection()
    
    # Fetch Entidades joining area and colectivo names
    entities = conn.execute("""
        SELECT e.*, a.nombre_area AS area, c.nombre_colectivo AS colectivo
        FROM entidad e
        LEFT JOIN area a ON e.id_area = a.id_area
        LEFT JOIN colectivo c ON e.id_colectivo = c.id_colectivo
    """).fetchall()
    
    # Fetch Servicios joining tipo_servicio names
    services = conn.execute("""
        SELECT s.*, ts.nombre_tipo_servicio AS tipo_servicio
        FROM servicios s
        LEFT JOIN tipo_servicio ts ON s.id_tipo_servicio = ts.id_tipo_servicio
    """).fetchall()
    
    # Fetch Documentacion
    docs = conn.execute("SELECT * FROM documentacion").fetchall()
    
    # Fetch filters (catalogs)
    areas = [dict(row) for row in conn.execute("SELECT id_area, nombre_area FROM area ORDER BY nombre_area").fetchall()]
    collectives = [dict(row) for row in conn.execute("SELECT id_colectivo, nombre_colectivo FROM colectivo ORDER BY nombre_colectivo").fetchall()]
    service_types = [dict(row) for row in conn.execute("SELECT id_tipo_servicio, nombre_tipo_servicio FROM tipo_servicio ORDER BY nombre_tipo_servicio").fetchall()]
    titularities = sorted(list(set(row['titularidad'] for row in conn.execute("SELECT DISTINCT titularidad FROM entidad WHERE titularidad IS NOT NULL").fetchall())))
    
    conn.close()
    
    # Build document mapping
    docs_by_service = {}
    for d in docs:
        s_id = d['id_servicio']
        docs_by_service.setdefault(s_id, []).append(d['nom_doc'])
        
    # Map services to frontend JSON keys
    services_list = []
    for s in services:
        s_dict = {
            "id": s['id_servicio'],
            "entidad_id": s['id_entidad'],
            "nombre": s['serv_prest'],
            "id_tipo_servicio": s['id_tipo_servicio'],
            "tipo_servicio": s['tipo_servicio'] or "Sin especificar",
            "tipo_registro": s['grupo_tipo'] or "servicio",
            "descripcion_corta": s['desc_servicio'],
            "descripcion_larga": s['descrip'],
            "plazas": s['n_plazas'],
            "cita_previa": s['cita'],
            "horario": s['horario'],
            "condiciones_admision": s['cond_admision'],
            "aportacion_beneficiario": s['aport_benefic'],
            "direccion": s['dir_serv'],
            "finalidad": s['fin_serv'],
            "documentacion": docs_by_service.get(s['id_servicio'], [])
        }
        services_list.append(s_dict)
        
    services_by_entity = {}
    for s in services_list:
        services_by_entity.setdefault(s['entidad_id'], []).append(s)
        
    # Map entities to frontend JSON keys
    entities_list = []
    for e in entities:
        e_dict = {
            "id": e['id_entidad'],
            "nombre": e['nombre'],
            "tipo_entidad": e['tip_ent'],
            "direccion": e['direccion'],
            "cp": e['cp'],
            "localidad": e['localidad'],
            "titularidad": e['titularidad'],
            "telefono": e['tfno'],
            "telefono2": e['tfno2'],
            "fax": e['fax'],
            "email": e['email'],
            "web": e['web'],
            "ceas": e['ceas'],
            "id_area": e['id_area'],
            "area": e['area'] or "Sin especificar",
            "id_colectivo": e['id_colectivo'],
            "colectivo": e['colectivo'] or "Sin especificar",
            "latitude": e['latitude'],
            "longitude": e['longitude'],
            "servicios": services_by_entity.get(e['id_entidad'], [])
        }
        entities_list.append(e_dict)
        
    return jsonify({
        "entidades": entities_list,
        "servicios_basicos": [], # Vacio, ya no se usan servicios basicos (ceas en mapa)
        "filters": {
            "areas": areas,
            "collectives": collectives,
            "service_types": service_types,
            "titularities": titularities
        }
    })


@app.route('/api/entidades', methods=['POST'])
@login_required
def create_entidad():
    data = request.json or {}
    nombre = data.get('nombre')
    if not nombre:
        return jsonify({"error": "El nombre es obligatorio"}), 400
        
    direccion = data.get('direccion')
    cp = data.get('cp')
    localidad = data.get('localidad', 'LEÓN')
    
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    use_manual_coords = False
    if lat is not None and lon is not None and str(lat).strip() != '' and str(lon).strip() != '':
        try:
            lat = float(lat)
            lon = float(lon)
            use_manual_coords = True
        except ValueError:
            pass
            
    if not use_manual_coords:
        try:
            from scripts.geocode_utils import GeocodingCache, get_coordinates
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="león_social_resources_app_v2")
            cache = GeocodingCache(CACHE_PATH)
            lat, lon = get_coordinates(geolocator, direccion, cp, localidad, cache)
        except Exception:
            lat, lon = 42.598726, -5.568412
            
    # Resolve IDs
    try:
        id_area = int(data.get('area')) if data.get('area') else None
    except ValueError:
        id_area = None
        
    try:
        id_colectivo = int(data.get('colectivo')) if data.get('colectivo') else None
    except ValueError:
        id_colectivo = None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO entidad 
    (nombre, tip_ent, direccion, cp, localidad, titularidad, tfno, tfno2, email, web, ceas, id_area, id_colectivo, latitude, longitude)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        nombre,
        data.get('tipo_entidad'),
        direccion,
        cp,
        localidad,
        data.get('titularidad'),
        data.get('telefono'),
        data.get('telefono2'),
        data.get('email'),
        data.get('web'),
        data.get('ceas'),
        id_area,
        id_colectivo,
        lat, lon
    ))
    new_id = cursor.lastrowid
    conn.commit()
    
    inserted = conn.execute("SELECT * FROM entidad WHERE id_entidad = ?", (new_id,)).fetchone()
    conn.close()
    
    return jsonify(dict(inserted)), 201


@app.route('/api/entidades/<int:ent_id>', methods=['PUT'])
@login_required
def update_entidad(ent_id):
    data = request.json or {}
    conn = get_db_connection()
    
    entity = conn.execute("SELECT * FROM entidad WHERE id_entidad = ?", (ent_id,)).fetchone()
    if not entity:
        conn.close()
        return jsonify({"error": "Entidad no encontrada"}), 404
        
    direccion = data.get('direccion', entity['direccion'])
    cp = data.get('cp', entity['cp'])
    localidad = data.get('localidad', entity['localidad'])
    
    lat = data.get('latitude')
    lon = data.get('longitude')
    
    use_manual_coords = False
    if lat is not None and lon is not None and str(lat).strip() != '' and str(lon).strip() != '':
        try:
            lat = float(lat)
            lon = float(lon)
            use_manual_coords = True
        except ValueError:
            pass
            
    if not use_manual_coords:
        lat, lon = entity['latitude'], entity['longitude']
        if (direccion != entity['direccion'] or cp != entity['cp'] or localidad != entity['localidad']):
            try:
                from scripts.geocode_utils import GeocodingCache, get_coordinates
                from geopy.geocoders import Nominatim
                geolocator = Nominatim(user_agent="león_social_resources_app_v2")
                cache = GeocodingCache(CACHE_PATH)
                lat, lon = get_coordinates(geolocator, direccion, cp, localidad, cache)
            except Exception:
                pass
                
    # Resolve IDs
    try:
        id_area = int(data.get('area')) if data.get('area') else None
    except ValueError:
        id_area = None
        
    try:
        id_colectivo = int(data.get('colectivo')) if data.get('colectivo') else None
    except ValueError:
        id_colectivo = None
        
    conn.execute("""
    UPDATE entidad SET
        nombre = ?, tip_ent = ?, direccion = ?, cp = ?, localidad = ?, titularidad = ?, 
        tfno = ?, tfno2 = ?, email = ?, web = ?, ceas = ?, id_area = ?, id_colectivo = ?, 
        latitude = ?, longitude = ?
    WHERE id_entidad = ?
    """, (
        data.get('nombre', entity['nombre']),
        data.get('tipo_entidad', entity['tip_ent']),
        direccion,
        cp,
        localidad,
        data.get('titularidad', entity['titularidad']),
        data.get('telefono', entity['tfno']),
        data.get('telefono2', entity['tfno2']),
        data.get('email', entity['email']),
        data.get('web', entity['web']),
        data.get('ceas', entity['ceas']),
        id_area,
        id_colectivo,
        lat, lon, ent_id
    ))
    conn.commit()
    
    updated = conn.execute("SELECT * FROM entidad WHERE id_entidad = ?", (ent_id,)).fetchone()
    conn.close()
    
    return jsonify(dict(updated))


@app.route('/api/entidades/<int:ent_id>', methods=['DELETE'])
@login_required
def delete_entidad(ent_id):
    conn = get_db_connection()
    entity = conn.execute("SELECT * FROM entidad WHERE id_entidad = ?", (ent_id,)).fetchone()
    if not entity:
        conn.close()
        return jsonify({"error": "Entidad no encontrada"}), 404
        
    # CASCADE is not active by default in SQLite unless pragma foreign_keys is ON.
    # To be safe, we delete services and docs manually or run PRAGMA.
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("DELETE FROM entidad WHERE id_entidad = ?", (ent_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Entidad eliminada correctamente."})


@app.route('/api/servicios', methods=['POST'])
@login_required
def create_servicio():
    data = request.json or {}
    entidad_id = data.get('entidad_id')
    nombre = data.get('nombre')
    
    if not entidad_id or not nombre:
        return jsonify({"error": "El nombre y el ID de la entidad son obligatorios"}), 400
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if entity exists
    entity = conn.execute("SELECT id_entidad FROM entidad WHERE id_entidad = ?", (entidad_id,)).fetchone()
    if not entity:
        conn.close()
        return jsonify({"error": "Entidad no encontrada"}), 404
        
    # Resolve tipo_servicio to ID
    try:
        id_tipo_servicio = int(data.get('tipo_servicio')) if data.get('tipo_servicio') else None
    except ValueError:
        id_tipo_servicio = None
        
    cursor.execute("""
    INSERT INTO servicios
    (id_entidad, serv_prest, grupo_tipo, desc_servicio, descrip, n_plazas, cita, horario, cond_admision, aport_benefic, dir_serv, fin_serv, id_tipo_servicio)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entidad_id,
        nombre,
        data.get('tipo_registro', 'servicio'),
        data.get('descripcion_corta'),
        data.get('descripcion_larga'),
        data.get('plazas'),
        data.get('cita_previa'),
        data.get('horario'),
        data.get('condiciones_admision'),
        data.get('aportacion_beneficiario'),
        data.get('direccion'),
        data.get('finalidad'),
        id_tipo_servicio
    ))
    new_id = cursor.lastrowid
    
    # Process required documentation
    docs = data.get('documentacion', [])
    for doc in docs:
        if str(doc).strip():
            cursor.execute("INSERT INTO documentacion (id_servicio, nom_doc) VALUES (?, ?)", (new_id, str(doc).strip()))
            
    conn.commit()
    
    # Fetch inserted
    inserted = conn.execute("SELECT * FROM servicios WHERE id_servicio = ?", (new_id,)).fetchone()
    inserted_dict = dict(inserted)
    inserted_dict['documentacion'] = docs
    
    conn.close()
    return jsonify(inserted_dict), 201


@app.route('/api/servicios/<int:serv_id>', methods=['PUT'])
@login_required
def update_servicio(serv_id):
    data = request.json or {}
    conn = get_db_connection()
    
    service = conn.execute("SELECT * FROM servicios WHERE id_servicio = ?", (serv_id,)).fetchone()
    if not service:
        conn.close()
        return jsonify({"error": "Servicio no encontrado"}), 404
        
    # Resolve tipo_servicio to ID
    try:
        id_tipo_servicio = int(data.get('tipo_servicio')) if data.get('tipo_servicio') else None
    except ValueError:
        id_tipo_servicio = None
        
    conn.execute("""
    UPDATE servicios SET
        serv_prest = ?, grupo_tipo = ?, desc_servicio = ?, 
        descrip = ?, n_plazas = ?, cita = ?, horario = ?, 
        cond_admision = ?, aport_benefic = ?, dir_serv = ?, fin_serv = ?, 
        id_tipo_servicio = ?
    WHERE id_servicio = ?
    """, (
        data.get('nombre', service['serv_prest']),
        data.get('tipo_registro', service['grupo_tipo']),
        data.get('descripcion_corta', service['desc_servicio']),
        data.get('descripcion_larga', service['descrip']),
        data.get('plazas', service['n_plazas']),
        data.get('cita_previa', service['cita']),
        data.get('horario', service['horario']),
        data.get('condiciones_admision', service['cond_admision']),
        data.get('aportacion_beneficiario', service['aport_benefic']),
        data.get('direccion', service['dir_serv']),
        data.get('finalidad', service['fin_serv']),
        id_tipo_servicio,
        serv_id
    ))
    
    # Update documents
    if 'documentacion' in data:
        conn.execute("DELETE FROM documentacion WHERE id_servicio = ?", (serv_id,))
        for doc in data['documentacion']:
            if str(doc).strip():
                conn.execute("INSERT INTO documentacion (id_servicio, nom_doc) VALUES (?, ?)", (serv_id, str(doc).strip()))
                
    conn.commit()
    
    # Fetch updated
    updated = conn.execute("SELECT * FROM servicios WHERE id_servicio = ?", (serv_id,)).fetchone()
    updated_dict = dict(updated)
    
    updated_docs = conn.execute("SELECT nom_doc FROM documentacion WHERE id_servicio = ?", (serv_id,)).fetchall()
    updated_dict['documentacion'] = [d['nom_doc'] for d in updated_docs]
    
    conn.close()
    return jsonify(updated_dict)


@app.route('/api/servicios/<int:serv_id>', methods=['DELETE'])
@login_required
def delete_servicio(serv_id):
    conn = get_db_connection()
    service = conn.execute("SELECT * FROM servicios WHERE id_servicio = ?", (serv_id,)).fetchone()
    if not service:
        conn.close()
        return jsonify({"error": "Servicio no encontrado"}), 404
        
    conn.execute("DELETE FROM servicios WHERE id_servicio = ?", (serv_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Servicio eliminado correctamente."})


# --- ADMIN USER ROUTING ---
@app.route('/api/users', methods=['GET'])
@login_required
def list_users():
    conn = get_db_connection()
    users = conn.execute("SELECT id, username, email, created_at FROM users").fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])


@app.route('/api/users', methods=['POST'])
@login_required
def create_user():
    data = request.json or {}
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({"error": "Faltan campos obligatorios"}), 400
        
    # Highly secure PBKDF2 with 600k iterations
    hashed = generate_password_hash(password, method="pbkdf2:sha256:600000")
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed)
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({
            "id": new_id,
            "username": username,
            "email": email
        }), 201
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "El nombre de usuario o correo electrónico ya existe."}), 400


@app.route('/api/users/<int:u_id>', methods=['DELETE'])
@login_required
def delete_user(u_id):
    if u_id == session['user_id']:
        return jsonify({"error": "No puede eliminarse a sí mismo."}), 400
        
    conn = get_db_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (u_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Usuario no encontrado"}), 404
        
    conn.execute("DELETE FROM users WHERE id = ?", (u_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Usuario administrador eliminado."})


@app.route('/api/users/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.json or {}
    old_password = data.get('old_password')
    new_password = data.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({"error": "Faltan campos"}), 400
        
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    
    if not check_password_hash(user['password_hash'], old_password):
        conn.close()
        return jsonify({"error": "Contraseña actual incorrecta."}), 400
        
    hashed = generate_password_hash(new_password, method="pbkdf2:sha256:600000")
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({"message": "Contraseña actualizada con éxito."})


# --- DEVELOPMENT ONLY STATIC FILE ROUTING ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_static(path):
    if not path:
        path = 'index.html'
    
    static_dir = os.path.join(WORKSPACE_DIR, 'app', 'static')
    if os.path.exists(os.path.join(static_dir, path)):
        return send_from_directory(static_dir, path)
    
    # Fallback to index if path has no dot (SPA style redirect)
    if '.' not in path:
        return send_from_directory(static_dir, 'index.html')
        
    return "File not found", 404


if __name__ == '__main__':
    # Local dev server runs on port 8001
    app.run(host='0.0.0.0', port=8001, debug=True)
