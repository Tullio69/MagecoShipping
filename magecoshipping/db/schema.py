import sqlite3
from pathlib import Path

# Percorso del database
DB_PATH = Path(__file__).resolve().parent / "database.sqlite3"

def init_db():
    """
    Crea il database SQLite e le tabelle se non esistono.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Tabella principale con i dati delle fatture elaborate
        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            cliente TEXT,
            piva_cliente TEXT,
            tratta TEXT,
            costo REAL,
            status TEXT,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Tabella di log degli eventi
        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        print(f"✅ Database inizializzato in: {DB_PATH}")
