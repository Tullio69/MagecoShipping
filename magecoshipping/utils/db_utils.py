import sqlite3
from pathlib import Path
import json

DB_PATH = Path(__file__).resolve().parents[1] / "db" / "database.sqlite3"


def init_db():
    """Crea le tabelle se non esistono già."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Tabella fornitori
    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            denominazione TEXT NOT NULL,
            piva TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tabella documenti
    cur.execute("""
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

    # Tabella righe documento
    cur.execute("""
        CREATE TABLE IF NOT EXISTS document_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER,
            descrizione_rigo TEXT,
            tratta TEXT,
            targa TEXT,
            tipo_veicolo TEXT,
            costo REAL,
            recognized INTEGER DEFAULT 0,
            include INTEGER DEFAULT 1,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)

    conn.commit()
    conn.close()


def insert_or_get_supplier(fornitore: str, piva_fornitore: str) -> int:
    """
    Cerca un fornitore per P.IVA. Se non esiste, lo crea.
    Ritorna l'ID del fornitore.
    """
    if not fornitore or not piva_fornitore:
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id FROM suppliers WHERE piva = ?", (piva_fornitore,))
    row = cur.fetchone()
    if row:
        supplier_id = row[0]
    else:
        cur.execute(
            "INSERT INTO suppliers (denominazione, piva) VALUES (?, ?)",
            (fornitore, piva_fornitore)
        )
        supplier_id = cur.lastrowid
        conn.commit()

    conn.close()
    return supplier_id


def insert_document(data: dict):
    """
    Inserisce un documento e le sue righe nel database.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Inserimento documento
    cur.execute("""
        INSERT INTO documents (
            file_name, cliente, piva_cliente,
            fornitore, piva_fornitore, supplier_id,
            data_doc, num_doc, totale_doc,
            status, original_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("file_name"),
        data.get("cliente"),
        data.get("piva_cliente"),
        data.get("fornitore"),
        data.get("piva_fornitore"),
        data.get("supplier_id"),
        data.get("data_doc"),
        data.get("num_doc"),
        data.get("totale_doc"),
        data.get("status"),
        data.get("original_path")
    ))

    document_id = cur.lastrowid

    # Inserimento righe documento
    for line in data.get("lines", []):
        cur.execute("""
            INSERT INTO document_lines (
                document_id, descrizione_rigo, tratta, targhe,
                tipo_veicolo, quantita_fattura, quantita_reale,
                costo, recognized, include
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            line.get("descrizione_rigo"),
            line.get("tratta"),
            line.get("targhe"),
            line.get("tipo_veicolo"),
            float(line.get("quantita_fattura", 1.0)),
            float(line.get("quantita_reale", 1.0)),
            float(line.get("costo", 0)),
            int(line.get("recognized", False)),
            int(line.get("include", True))
        ))

    conn.commit()
    conn.close()
    print(f"✅ Documento '{data.get('file_name')}' e {len(data.get('lines', []))} righe salvate nel database.")

import sqlite3
from magecoshipping.db.schema import DB_PATH

def get_documents(filter_text: str = "") -> list[dict]:
    """
    Restituisce la lista dei documenti dal DB, con filtro opzionale per cliente / fornitore / P.IVA.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if filter_text:
        ft = f"%{filter_text}%"
        cur.execute("""
            SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
                   data_doc, num_doc, totale_doc, status, date_added
            FROM documents
            WHERE cliente LIKE ? OR fornitore LIKE ? OR piva_cliente LIKE ? OR piva_fornitore LIKE ?
            ORDER BY date_added DESC
        """, (ft, ft, ft, ft))
    else:
        cur.execute("""
            SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
                   data_doc, num_doc, totale_doc, status, date_added
            FROM documents
            ORDER BY date_added DESC
        """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# Inizializza il DB alla prima importazione
init_db()
