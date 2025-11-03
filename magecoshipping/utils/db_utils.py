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


def insert_document(data: dict, batch_id: int = None):
    """
    Inserisce un documento completo nel database, comprese le righe.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Inserisci documento
    cur.execute("""
        INSERT INTO documents (
            file_name, cliente, piva_cliente, fornitore, piva_fornitore,
            num_doc, data_doc, totale_doc, status, supplier_id, batch_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        batch_id,
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
# 🔹 Funzioni per gestire i batch
# ======================================

def create_batch(batch_name: str, num_documents: int = 0) -> int:
    """
    Crea un nuovo batch di acquisizione.
    Ritorna l'ID del batch.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO batches (batch_name, num_documents, status)
        VALUES (?, ?, 'pending')
    """, (batch_name, num_documents))

    batch_id = cur.lastrowid
    conn.commit()
    conn.close()
    return batch_id


def get_batch(batch_id: int) -> dict | None:
    """
    Recupera un batch per ID.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, batch_name, num_documents, status, created_at
        FROM batches
        WHERE id = ?
    """, (batch_id,))

    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_batches(status_filter: str = None) -> list[dict]:
    """
    Recupera tutti i batch, opzionalmente filtrati per status.
    """
    conn = get_connection()
    cur = conn.cursor()

    sql = "SELECT id, batch_name, num_documents, status, created_at FROM batches WHERE 1=1"
    params = []

    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter)

    sql += " ORDER BY created_at DESC"

    cur.execute(sql, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def update_batch_status(batch_id: int, status: str):
    """
    Aggiorna lo status di un batch.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE batches
        SET status = ?
        WHERE id = ?
    """, (status, batch_id))

    conn.commit()
    conn.close()


def get_documents_by_batch(batch_id: int) -> list[dict]:
    """
    Recupera tutti i documenti appartenenti a un batch.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
               data_doc, num_doc, totale_doc, status, created_at
        FROM documents
        WHERE batch_id = ?
        ORDER BY created_at
    """, (batch_id,))

    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ======================================
# 🔹 Funzioni di lettura e query
# ======================================

def get_documents(filter_text: str = "", status_filter: str | None = None) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()

    sql = """
        SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
               data_doc, num_doc, totale_doc, status, created_at
        FROM documents
        WHERE 1=1
    """
    params = []

    if filter_text:
        sql += " AND (cliente LIKE ? OR fornitore LIKE ? OR piva_cliente LIKE ? OR piva_fornitore LIKE ?)"
        ft = f"%{filter_text}%"
        params += [ft, ft, ft, ft]

    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter)

    sql += " ORDER BY created_at DESC"

    cur.execute(sql, params)
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

