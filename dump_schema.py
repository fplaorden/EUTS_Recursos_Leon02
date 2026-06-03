import sqlite3
import os

db_file = "Recursos_TS_Leon.db"
output_file = "db_schema_output.txt"

def dump_schema():
    if not os.path.exists(db_file):
        print(f"Error: {db_file} not found!")
        return
        
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("=== DATABASE TABLES AND COLUMNS ===\n")
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        
        for table in tables:
            f.write(f"\nTable: {table}\n")
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            for col in columns:
                # col format: (cid, name, type, notnull, dflt_value, pk)
                f.write(f"  Column: {col[1]} ({col[2]}){' [PK]' if col[5] else ''}{' [NOT NULL]' if col[3] else ''}\n")
                
            # Get sample data
            f.write("  Sample row:\n")
            cursor.execute(f"SELECT * FROM {table} LIMIT 1;")
            row = cursor.fetchone()
            if row:
                f.write(f"    {dict(zip([c[1] for c in columns], row))}\n")
            else:
                f.write("    (Empty)\n")
                
        # Get foreign keys info
        f.write("\n=== FOREIGN KEY RELATIONSHIPS ===\n")
        for table in tables:
            cursor.execute(f"PRAGMA foreign_key_list({table});")
            fks = cursor.fetchall()
            if fks:
                f.write(f"\nTable: {table}\n")
                for fk in fks:
                    # fk format: (id, seq, table, from, to, on_update, on_delete, match)
                    f.write(f"  {table}.{fk[3]} -> {fk[2]}.{fk[4]} (ON DELETE: {fk[6]})\n")
                    
    conn.close()
    print(f"Schema dumped to {output_file}")

if __name__ == "__main__":
    dump_schema()
