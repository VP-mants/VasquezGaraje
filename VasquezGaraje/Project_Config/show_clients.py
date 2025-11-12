import sqlite3
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
p = BASE_DIR / 'Project_Config' / 'DBVasquezGaraje.db'
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT cliente_id, nombre_cliente, apellido_cliente, correo_cliente FROM CLIENTE LIMIT 20")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
