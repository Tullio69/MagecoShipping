import sqlite3
from pathlib import Path

# Percorso del database
DB_PATH = Path(__file__).resolve().parent / "database.sqlite3"

def init_db():
    """
    Crea o aggiorna il database SQLite con le tabelle aggiornate.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Tabella fornitori
        c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fornitore TEXT NOT NULL,
            piva_fornitore TEXT DEFAULT 'N/D',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Tabella documenti
        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            cliente TEXT NOT NULL,
            piva_cliente TEXT DEFAULT 'N/D',
            fornitore TEXT NOT NULL,
            piva_fornitore TEXT DEFAULT 'N/D',
            num_doc TEXT,
            data_doc TEXT,
            totale_doc REAL,
            status TEXT DEFAULT 'pending' NOT NULL,
            supplier_id INTEGER,
            original_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
        )
        """)

        # Tabella righe documento
        c.execute("""
        CREATE TABLE IF NOT EXISTS document_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            descrizione_rigo TEXT,
            tratta TEXT,
            targhe TEXT,
            tipo_veicolo TEXT,
            quantita_fattura REAL,
            quantita_reale REAL,
            costo REAL,
            recognized INTEGER DEFAULT 0,
            include INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(document_id) REFERENCES documents(id)
        )
        """)

        # Tabella di log
        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()
        print(f"✅ Database inizializzato in: {DB_PATH}")

if __name__ == "__main__":
    print("🚀 Avvio inizializzazione database MagecoShipping...")
    init_db()
