import sqlite3
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
 p = BASE_DIR / 'Project_Config' / 'DBVasquezGaraje.db'
conn = sqlite3.connect(str(p))
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cur.fetchall())
conn.close()
