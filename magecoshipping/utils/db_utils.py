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
    Accetta sia il payload già 'mappato' (num_doc, data_doc, totale_doc, lines con chiavi DB),
    sia il payload grezzo dal parser (document{numero,data,totale}, lines con {descrizione, quantita, prezzo, targhe(list), tipo_veicolo}).
    """
    conn = get_connection()
    cur = conn.cursor()

    # --- Normalizzazione document-level ---
    num_doc = data.get("num_doc")
    data_doc = data.get("data_doc")
    totale_doc = data.get("totale_doc") or data.get("costo")

    # Se arriva la struttura dal parser: document = {numero, data, totale, divisa}
    if not num_doc or not data_doc or totale_doc is None:
        doc = data.get("document", {}) or {}
        num_doc = num_doc or doc.get("numero")
        data_doc = data_doc or doc.get("data")
        if totale_doc is None:
            totale_doc = doc.get("totale")

    cur.execute("""
        INSERT INTO documents (
            file_name, cliente, piva_cliente, fornitore, piva_fornitore,
            num_doc, data_doc, totale_doc, status, supplier_id, original_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("file_name"),
        data.get("cliente"),
        data.get("piva_cliente"),
        data.get("fornitore"),
        data.get("piva_fornitore"),
        num_doc,
        data_doc,
        totale_doc,
        data.get("status", "pending"),
        data.get("supplier_id"),
        data.get("original_path"),
    ))
    document_id = cur.lastrowid

    # --- Normalizzazione righe ---
    lines = data.get("lines", []) or []
    for raw in lines:
        # Accetta sia chiavi "nuove" (DB) sia quelle del parser
        descrizione_rigo = raw.get("descrizione_rigo") or raw.get("descrizione") or ""
        tratta = raw.get("tratta")
        tipo_veicolo = raw.get("tipo_veicolo") or raw.get("veicolo_tipo")  # nel dubbio
        # targhe: il parser può dare LISTA; il DB vuole TEXT
        targhe_val = raw.get("targhe")
        if isinstance(targhe_val, list):
            targhe = ";".join([str(t).strip().upper() for t in targhe_val if str(t).strip()])
        else:
            targhe = (targhe_val or "").strip()

        # quantità/costo: forziamo regole -> quantità sempre 1, costo dal campo giusto
        quantita_fattura = raw.get("quantita_fattura")
        if quantita_fattura is None:
            quantita_fattura = raw.get("quantita", 1)  # dal parser
        quantita_reale = raw.get("quantita_reale", 1)

        costo = raw.get("costo")
        if costo is None:
            # dal parser arriva come 'prezzo'
            prezzo = raw.get("prezzo")
            costo = float(prezzo) if prezzo is not None else 0.0

        # recognized/include: default sensati
        recognized = int(raw.get("recognized", 1 if (tipo_veicolo and tipo_veicolo != "N/D") else 0))
        include = int(raw.get("include", 1))

        cur.execute("""
            INSERT INTO document_lines (
                document_id, descrizione_rigo, tratta, targhe, tipo_veicolo,
                quantita_fattura, quantita_reale, costo, recognized, include
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            descrizione_rigo,
            tratta,
            targhe,
            tipo_veicolo,
            1,                 # regola: sempre 1
            1,                 # regola: sempre 1
            float(costo or 0),
            recognized,
            include,
        ))

    conn.commit()
    conn.close()
    return document_id



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

