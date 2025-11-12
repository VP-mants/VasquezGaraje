import sqlite3
p = r'C:\Users\HP Omen\Desktop\VasquezGaraje\Home\DBVazquezGaraje.db'
conn = sqlite3.connect(p)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cur.fetchall())
conn.close()
