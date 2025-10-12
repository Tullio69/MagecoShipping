import sqlite3
from pathlib import Path
from magecoshipping.db.schema import DB_PATH
import os
import datetime

# ============================================================
# CONNESSIONE DI BASE
# ============================================================

def get_connection():
    """Restituisce una connessione aperta al database SQLite."""
    return sqlite3.connect(DB_PATH)


# ============================================================
# INSERIMENTO DOCUMENTI E LOG EVENTI (CODICE ORIGINALE)
# ============================================================

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


# ============================================================
# INIZIALIZZAZIONE / AGGIORNAMENTO STRUTTURA DATABASE
# ============================================================

def init_database():
    """
    Crea o aggiorna la struttura del database MagecoShipping.
    Deve essere eseguita una volta all'avvio dell'applicazione.
    """
    db_file = Path(DB_PATH)
    os.makedirs(db_file.parent, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # === Tabella fornitori ===
    c.execute("""
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        vat_number TEXT UNIQUE NOT NULL,
        address TEXT,
        city TEXT,
        province TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # === Verifica colonne nella tabella documents ===
    c.execute("PRAGMA table_info(documents);")
    existing_cols = [row[1] for row in c.fetchall()]

    if "supplier_id" not in existing_cols:
        try:
            c.execute("ALTER TABLE documents ADD COLUMN supplier_id INTEGER;")
            print("🧱 Campo supplier_id aggiunto a 'documents'.")
        except sqlite3.OperationalError:
            pass  # La colonna esiste già o non è modificabile

    # === Tabella shipments (per i dati viaggio) ===
    c.execute("""
    CREATE TABLE IF NOT EXISTS shipments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER,
        travel_date TEXT,
        tratta TEXT,
        veicolo_tipo TEXT,
        targa_motrice TEXT,
        targa_rimorchio TEXT,
        num_mezzi INTEGER,
        costo_imponibile REAL,
        descrizione TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database inizializzato o aggiornato in {DB_PATH}")


# ============================================================
# GESTIONE FORNITORI
# ============================================================

def get_or_create_supplier(vat_number: str, name: str, address=None, city=None, province=None) -> int:
    """
    Ritorna l'ID del fornitore se esiste, altrimenti lo crea.
    """
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM suppliers WHERE vat_number = ?", (vat_number,))
        row = c.fetchone()
        if row:
            return row[0]

        c.execute("""
            INSERT INTO suppliers (name, vat_number, address, city, province)
            VALUES (?, ?, ?, ?, ?)
        """, (name, vat_number, address, city, province))
        conn.commit()
        new_id = c.lastrowid
        print(f"➕ Nuovo fornitore aggiunto: {name} (ID: {new_id})")
        return new_id

if __name__ == "__main__":
    print("🔍 Avvio inizializzazione database...")
    import sqlite3
    from magecoshipping.db.schema import DB_PATH

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in c.fetchall()]
    print(f"📦 Tabelle trovate: {tables}")
    conn.close()

    init_database()
