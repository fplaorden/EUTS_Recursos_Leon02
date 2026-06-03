import subprocess
import os
import sys
import time

def main():
    print("Iniciando depuración del servidor Flask en el puerto 8001...")
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(workspace_dir, "app", "server.py")
    log_file = os.path.join(workspace_dir, "server_log.txt")
    
    # Abrimos el archivo de log para escribir la salida
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=== LOG DE INICIO DEL SERVIDOR ===\n")
        f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Server path: {server_path}\n\n")
        
        try:
            # Ejecutamos el servidor como subproceso redirigiendo stdout/stderr al log
            process = subprocess.Popen(
                [sys.executable, server_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            f.write(f"Proceso iniciado con PID: {process.pid}\n")
            f.flush()
            
            # Esperamos 5 segundos leyendo la salida
            start_time = time.time()
            while time.time() - start_time < 5:
                # Comprobamos si el proceso ha terminado
                if process.poll() is not None:
                    f.write("\nEl proceso ha terminado prematuramente.\n")
                    break
                # Leemos la salida si hay
                line = process.stdout.readline()
                if line:
                    f.write(line)
                    f.flush()
                    print(line.strip())
                    
            # Si sigue vivo, leemos lo que quede en el búfer
            f.write("\n--- Servidor activo tras 5 segundos ---\n")
            f.flush()
            
        except Exception as e:
            f.write(f"ERROR al lanzar el proceso: {e}\n")
            print(f"Error: {e}")
            
    print(f"Proceso de depuración completado. Revisa el log en {log_file}")

if __name__ == "__main__":
    main()
