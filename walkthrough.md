# Recorrido de Entrega: Asistencia Social León 02

Hemos creado una aplicación completamente nueva e independiente en el directorio **EUTS_Recursos_Leon02**, diseñada desde cero sobre la base de datos relacional normalizada y saneada `Recursos_TS_Leon.db`.

Esta versión no arrastra ningún dato o implementación errónea y cumple con estrictos estándares de seguridad y con los puertos asignados por el usuario.

---

## 🔒 Características de Seguridad de Nivel de Producción

1. **Cifrado de Credenciales**: Las contraseñas de los administradores se guardan utilizando el algoritmo **PBKDF2 con SHA-256 con 600,000 iteraciones** de seguridad (mediante `werkzeug.security`), lo que impide ataques de descifrado o fuerza bruta en la base de datos.
2. **Cookies de Sesión Seguras**: Las cookies de sesión para la autenticación en el panel administrativo tienen configurados los flags `HttpOnly` (previene robo de token por scripting malicioso XSS) y `SameSite='Lax'` (bloquea ataques CSRF de origen cruzado). El flag `Secure` se activa automáticamente en producción para restringir la sesión únicamente a conexiones TLS/HTTPS.
3. **Control Total de Conexiones (HTTPS)**: En producción, Nginx actúa como terminación SSL e interceptor de peticiones, escuchando en el puerto asignado **`8443`** y forzando la redirección automática de cualquier tráfico inseguro a HTTPS.
4. **Protección de Cabeceras**: Se inyectan cabeceras de seguridad HTTP robustas (`X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer-when-downgrade`) para proteger al cliente en su navegador.

---

## 🗺️ Geolocalización Inteligente en Segundo Plano

La base de datos normalizada original carecía de campos de latitud y longitud. Hemos implementado la siguiente solución automatizada:
* **Estructuración Dinámica**: Al arrancar, el servidor Flask realiza una inspección de la tabla `entidad` y añade automáticamente las columnas `latitude` y `longitude` si no existen.
* **Hilo en Segundo Plano (Background Thread)**: Para no demorar ni bloquear el inicio del servidor, se lanza un subproceso asíncrono que busca todas las entidades sin coordenadas asignadas, las geolocaliza usando Nominatim (OpenStreetMap) aplicando filtros de limpieza de dirección, y las almacena de forma persistente en la base de datos.
* **Caché Local**: Se utiliza el archivo `geocoding_cache.json` para no consumir peticiones repetitivas de red ante posteriores reinicios.
* **Ajuste Manual**: Desde el panel de administración, el administrador puede editar cualquier entidad y definir manualmente coordenadas precisas (latitud y longitud) en campos dedicados para omitir el cálculo automático.

---

## 📁 Estructura del Código Creado

La aplicación cuenta con los siguientes componentes en [EUTS_Recursos_Leon02](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02):

* [requirements.txt](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/requirements.txt): Dependencias necesarias (Flask, geopy, openpyxl, gunicorn, etc.).
* [run_server.py](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/run_server.py): Lanzador de la aplicación en desarrollo local.
* [scripts/geocode_utils.py](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/scripts/geocode_utils.py): Sanitizador y geocodificador de direcciones.
* [app/server.py](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/server.py): Servidor Flask backend. Inicializa las tablas de usuarios y de recuperación de contraseñas (`users` y `recovery_tokens`), maneja sesiones y expone los endpoints de la API mapeando los catálogos relacionales a objetos compatibles.
* **Frontend Estático**:
  - [index.html](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/static/index.html): SPA pública con mapa interactivo Leaflet.js.
  - [login.html](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/static/login.html): Interfaz segura para el login y la restauración por correo.
  - [admin.html](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/static/admin.html): Panel CRUD relacional para gestionar entidades, servicios y administradores.
  - [styles.css](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/static/styles.css): Hoja de estilos con soporte claro/oscuro e identidad de la Universidad de León.
  - [app.js](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/app/static/app.js): Lógica cliente (peticiones API, filtrado dinámico por IDs, render de marcadores).
* **Contenedores de Producción**:
  - [Dockerfile.app](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/Dockerfile.app): Empaqueta el backend en puerto `8001`.
  - [Dockerfile.nginx](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/Dockerfile.nginx): Crea el proxy con SSL auto-firmado de un año y copia el frontend.
  - [nginx.conf](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/nginx.conf): Proxy inverso SSL escuchando en el puerto **`8443`**.
  - [docker-compose.yml](file:///g:/Mi%20unidad/Antigravity_fpl/EUTS_Recursos_Leon02/docker-compose.yml): Orquesta la aplicación, mapea el puerto **`8443`** y monta el volumen persistente `social_db` para la base de datos sqlite.

---

## 🛠️ Resolución del Problema de las Chinchetas y Depuración

Durante las pruebas, se detectó que los marcadores del mapa no se dibujaban en el cliente. Esto se resolvió identificando y corrigiendo dos factores:
1. **Base de Datos Desactualizada**: El script de geolocalización original actualizó el archivo de base de datos en la raíz del proyecto (`Recursos_TS_Leon.db`). Sin embargo, el servidor Flask ejecuta su base de datos activa desde `data/Recursos_TS_Leon.db` para posibilitar el volumen persistente en Docker. Hemos añadido una validación al inicio del servidor en `app/server.py` que comprueba si la base de datos de `data/` carece de coordenadas y, en tal caso, copia de forma segura la versión geolocalizada de la raíz.
2. **Carcasa de Claves de Coordenadas (Case-tolerance)**: Se adaptó `app/static/app.js` para aceptar tanto `latitude` / `longitude` en minúsculas (servidor del puerto 8001) como `Latitude` / `Longitude` en mayúsculas (servidor antiguo del puerto 8000), evitando fallos silenciosos al mezclar llamadas.
3. **Limpieza del Workspace**: Se ha creado un script automatizado `cleanup.py` que elimina todos los scripts auxiliares de depuración de puertos, API, y esquemas que fueron generados para resolver el problema (`api_output_debug.txt`, `check_coords.py`, `inspect_db.py`, etc.).

---

## 🚀 Instrucciones de Ejecución

### 1. En Desarrollo (Local)

Para ejecutar la aplicación localmente:
1. Ejecuta el script de limpieza si deseas remover los ficheros auxiliares ya no necesarios:
   ```bash
   python cleanup.py
   ```
2. Inicia la aplicación ejecutando en la raíz de tu proyecto:
   ```bash
   python run_server.py
   ```
3. Esto levantará el servidor Flask en `http://localhost:8001` y abrirá automáticamente tu navegador en la interfaz pública:
   [http://localhost:8001/static/index.html](http://localhost:8001/static/index.html)
4. **Acceso de Administrador**:
   - Pulsa en **Acceso Administrador** en la parte superior derecha.
   - Introduce las credenciales seguras por defecto creadas automáticamente:
     * **Email**: `admin@leon.es`
     * **Contraseña**: `admin_password_change_me`
   - *Consejo*: Una vez dentro, haz clic en el icono de la llave para cambiar tu contraseña por una personalizada y segura.

### 2. En Producción (VPS)

Para desplegar en tu VPS de manera automatizada:
1. Copia los archivos del proyecto al servidor.
2. Asegúrate de tener Docker instalado en el VPS:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-v2
   ```
3. Ejecuta el comando de composición en la raíz:
   ```bash
   sudo docker compose up --build -d
   ```
4. La aplicación creará un volumen de almacenamiento persistente para la base de datos en `/app/data/` (dentro del contenedor) y estará disponible con HTTPS seguro a través de la IP de tu VPS en el puerto **`8443`**:
   `https://<IP-DE-TU-VPS>:8443/static/index.html`
5. El sistema redirigirá de manera forzada a HTTPS segura por dicho puerto cualquier intento de acceso HTTP.
