import sqlite3
from pathlib import Path
from magecoshipping.db.schema import DB_PATH

def get_connection():
    """Restituisce una connessione aperta al database SQLite."""
    return sqlite3.connect(DB_PATH)

def insert_document(data: dict):
    """
    Inserisce un record nella tabella documents.
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO documents (file_name, cliente, piva_cliente, tratta, costo, status)
            VALUES (:file_name, :cliente, :piva_cliente, :tratta, :costo, :status)
        """, data)
        conn.commit()
        print(f"💾 Documento salvato su DB: {data['file_name']}")

def log_event(event: str, message: str):
    """
    Inserisce un evento nel log.
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO logs (event, message)
            VALUES (?, ?)
        """, (event, message))
        conn.commit()
