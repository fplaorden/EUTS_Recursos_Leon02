import subprocess
import webbrowser
import time
import sys
import os

def run():
    print("Starting León Social Assistance Resources local server...")
    
    # Path to server.py
    workspace_dir = os.path.dirname(os.path.abspath(__file__))
    server_path = os.path.join(workspace_dir, "app", "server.py")
    
    # Run server.py as a subprocess
    process = None
    try:
        process = subprocess.Popen([sys.executable, server_path])
        
        # Give the server a moment to start up
        time.sleep(2.0)
        
        # Open browser
        url = "http://localhost:8001/index.html"
        print(f"Opening browser at: {url}")
        webbrowser.open(url)
        
        # Keep main thread alive and wait
        process.wait()
        
    except KeyboardInterrupt:
        print("\nStopping local server...")
        if process:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        print("Server stopped.")
    except Exception as e:
        print(f"Error running server: {e}")
        if process:
            process.kill()

if __name__ == "__main__":
    run()
