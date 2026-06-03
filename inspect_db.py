import sqlite3

def inspect():
    conn = sqlite3.connect("Recursos_TS_Leon.db")
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in Recursos_TS_Leon.db:")
    for t in tables:
        name = t[0]
        print(f"\nTable: {name}")
        cursor.execute(f"PRAGMA table_info({name});")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  Col: {col[1]} ({col[2]})")
            
    conn.close()

if __name__ == '__main__':
    inspect()
