import sqlite3
p = r'C:\Users\HP Omen\Desktop\VasquezGaraje\Home\DBVazquezGaraje.db'
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT cliente_id, nombre_cliente, apellido_cliente, correo_cliente FROM CLIENTE LIMIT 20")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
