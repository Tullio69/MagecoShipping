import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "database.sqlite3"
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
with open("schema.sql", "r", encoding="utf-8") as f:
    cur.executescript(f.read())
conn.commit()
conn.close()
print("✅ Database ricreato da schema.sql")
