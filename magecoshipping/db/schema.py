import sqlite3
from pathlib import Path

# Percorso del database
DB_PATH = Path(__file__).resolve().parent / "database.sqlite3"

def init_db():
    """
    Crea il database SQLite e tutte le tabelle secondo lo schema MagecoShipping v1.2.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        # Abilita chiavi esterne
        c.execute("PRAGMA foreign_keys = ON;")

        # ==========================================================
        #  TABELLA: suppliers (Anagrafica fornitori)
        # ==========================================================
        c.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            denominazione TEXT NOT NULL,
            piva TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ==========================================================
        #  TABELLA: documents (Testata dei documenti)
        # ==========================================================
        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            cliente TEXT,
            piva_cliente TEXT,
            fornitore TEXT,
            piva_fornitore TEXT,
            supplier_id INTEGER,
            data_doc TEXT,
            num_doc TEXT,
            totale_doc REAL,
            status TEXT,
            original_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        )
        """)

        # ==========================================================
        #  TABELLA: document_lines (Righe di dettaglio documento)
        # ==========================================================
        c.execute("""
        CREATE TABLE IF NOT EXISTS document_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            descrizione_rigo TEXT,
            tratta TEXT,
            targhe TEXT,
            tipo_veicolo TEXT,
            quantita_fattura REAL DEFAULT 1,
            quantita_reale REAL DEFAULT 1,
            costo REAL DEFAULT 0,
            recognized INTEGER DEFAULT 0,
            include INTEGER DEFAULT 1,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
        """)

        # ==========================================================
        #  TABELLA: logs (Storico eventi e notifiche)
        # ==========================================================
        c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # ==========================================================
        #  INDICI (per performance)
        # ==========================================================
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_cliente ON documents (cliente)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_documents_fornitore ON documents (fornitore)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lines_document_id ON document_lines (document_id)")

        # ==========================================================
        #  VIEW: v_document_full (documenti + righe)
        # ==========================================================
        c.execute("""
        CREATE VIEW IF NOT EXISTS v_document_full AS
        SELECT
            d.id AS document_id,
            d.file_name,
            d.cliente,
            d.piva_cliente,
            d.fornitore,
            d.piva_fornitore,
            d.data_doc,
            d.num_doc,
            d.totale_doc,
            d.status,
            l.id AS line_id,
            l.descrizione_rigo,
            l.tratta,
            l.targhe,
            l.tipo_veicolo,
            l.quantita_fattura,
            l.quantita_reale,
            l.costo,
            l.recognized,
            l.include
        FROM documents d
        LEFT JOIN document_lines l ON l.document_id = d.id;
        """)

        conn.commit()
        print(f"✅ Database inizializzato in: {DB_PATH}")
if __name__ == "__main__":
    print("🚀 Avvio inizializzazione database MagecoShipping...")
    init_db()
