import sqlite3
from pathlib import Path
from magecoshipping.db.schema import DB_PATH


# ===============================
# 🔹 Funzioni di inizializzazione
# ===============================

def get_connection():
    """Crea e restituisce una connessione SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ======================================
# 🔹 Funzioni di inserimento e gestione
# ======================================

def insert_or_get_supplier(fornitore: str, piva_fornitore: str) -> int:
    """
    Verifica se un fornitore esiste, altrimenti lo crea.
    Ritorna l'ID del fornitore.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM suppliers WHERE piva_fornitore = ?", (piva_fornitore,))
    row = cur.fetchone()
    if row:
        supplier_id = row["id"]
    else:
        cur.execute(
            "INSERT INTO suppliers (fornitore, piva_fornitore) VALUES (?, ?)",
            (fornitore, piva_fornitore)
        )
        supplier_id = cur.lastrowid
        conn.commit()

    conn.close()
    return supplier_id


def insert_document(data: dict):
    """
    Inserisce un documento completo nel database, comprese le righe.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Inserisci documento
    cur.execute("""
        INSERT INTO documents (
            file_name, cliente, piva_cliente, fornitore, piva_fornitore,
            num_doc, data_doc, totale_doc, status, supplier_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("file_name"),
        data.get("cliente"),
        data.get("piva_cliente"),
        data.get("fornitore"),
        data.get("piva_fornitore"),
        data.get("num_doc"),
        data.get("data_doc"),
        data.get("totale_doc") or data.get("costo"),
        data.get("status", "pending"),
        data.get("supplier_id"),
    ))

    document_id = cur.lastrowid

    # Inserisci righe associate (se presenti)
    lines = data.get("lines", [])
    for line in lines:
        cur.execute("""
            INSERT INTO document_lines (
                document_id, descrizione_rigo, tratta, targhe, tipo_veicolo,
                quantita_fattura, quantita_reale, costo, recognized, include
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            line.get("descrizione_rigo"),
            line.get("tratta"),
            line.get("targhe"),
            line.get("tipo_veicolo"),
            line.get("quantita_fattura", 1),
            line.get("quantita_reale", 1),
            line.get("costo", 0),
            int(line.get("recognized", False)),
            int(line.get("include", True)),
        ))

    conn.commit()
    conn.close()
    return document_id


# ======================================
# 🔹 Funzioni di lettura e query
# ======================================

def get_documents(filter_text: str = "") -> list[dict]:
    """
    Restituisce la lista dei documenti dal DB,
    con filtro opzionale per cliente / fornitore / P.IVA.
    """
    conn = get_connection()
    cur = conn.cursor()

    if filter_text:
        ft = f"%{filter_text}%"
        cur.execute("""
            SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
                   data_doc, num_doc, totale_doc, status, created_at
            FROM documents
            WHERE cliente LIKE ? OR fornitore LIKE ? OR piva_cliente LIKE ? OR piva_fornitore LIKE ?
            ORDER BY created_at DESC
        """, (ft, ft, ft, ft))
    else:
        cur.execute("""
            SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
                   data_doc, num_doc, totale_doc, status, created_at
            FROM documents
            ORDER BY created_at DESC
        """)

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows
