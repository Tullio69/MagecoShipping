import os
from pathlib import Path
import sqlite3
from magecoshipping.db.schema import DB_PATH, init_db

def reset_database():
    """
    Elimina il file database.sqlite3 e lo rigenera dallo schema.
    """
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"🗑️ Database eliminato: {DB_PATH}")

    # Ricrea da schema aggiornato
    init_db()
    print("✅ Nuovo database creato correttamente.")

if __name__ == "__main__":
    reset_database()
