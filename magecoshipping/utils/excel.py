# magecoshipping/utils/excel_utils.py

from pathlib import Path
from datetime import datetime
from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from magecoshipping.utils.db_utils import get_documents, get_connection


EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
EXPORTS_DIR.mkdir(exist_ok=True)


def query_records(filters: dict | None = None) -> list[dict]:
    """
    Recupera i record dal DB in base ai filtri.
    Supporta:
      - filters["ids"]: lista di ID selezionati
      - filters["q"] o filters["cliente"]: ricerca testuale
    """
    if not filters:
        return get_documents("")

    # 1️⃣ Se l’utente ha selezionato ID specifici
    if "ids" in filters and filters["ids"]:
        ids = [int(x) for x in filters["ids"] if str(x).isdigit()]
        if not ids:
            return []
        conn = get_connection()
        cur = conn.cursor()
        placeholders = ",".join("?" for _ in ids)
        sql = f"""
            SELECT id, file_name, cliente, piva_cliente, fornitore, piva_fornitore,
                   data_doc, num_doc, totale_doc, status, created_at
            FROM documents
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC
        """
        cur.execute(sql, ids)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # 2️⃣ Altrimenti usa il filtro testuale classico
    filter_text = (
        (filters.get("q") or "").strip()
        or (filters.get("cliente") or "").strip()
    )
    return get_documents(filter_text)

def generate_excel(records: list[dict], file_name: str | None = None) -> Path:
    """
    Genera un file Excel con i record forniti e restituisce il percorso completo.
    """
    if not records:
        raise ValueError("Nessun record fornito per l'esportazione.")

    # Generazione nome file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = file_name or f"mageco_export_{timestamp}.xlsx"
    output_path = EXPORTS_DIR / safe_name

    # Crea il workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Spedizioni"

    # Intestazioni colonne
    headers = list(records[0].keys())
    ws.append(headers)

    # Righe dati
    for rec in records:
        ws.append([rec.get(h, "") for h in headers])

    # Auto-dimensionamento colonne
    for i, col in enumerate(ws.columns, start=1):
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[get_column_letter(i)].width = min(max_len + 2, 40)

    # Salva file
    wb.save(output_path)
    return output_path


def export_filtered_excel(filters: dict | None = None) -> Path:
    """
    Shortcut che combina query + generazione Excel in un unico passaggio.
    """
    records = query_records(filters)
    return generate_excel(records)

"""
MagecoShipping - Modulo Excel Utility
----------------------------------------

Questo modulo gestisce la generazione dei file Excel contenenti i dati
delle spedizioni registrate nel database di MagecoShipping.

Strutturato per essere indipendente da Flask, può essere richiamato
sia da interfaccia web che da script o test automatizzati.

Funzioni principali:
--------------------

1. query_records(filters: dict | None = None) -> list[dict]
   Recupera i record dal database SQLite in base ai filtri specificati.
   Attualmente restituisce tutti i documenti (funzione stub da espandere).
   - Input: dizionario di filtri (es. {"cliente": "Tizio"})
   - Output: lista di record (ciascuno rappresentato da un dizionario)

2. generate_excel(records: list[dict], file_name: str | None = None) -> Path
   Crea un file Excel (.xlsx) con i dati forniti.
   - Usa openpyxl per generare il workbook.
   - Aggiunge automaticamente intestazioni e righe dati.
   - Ridimensiona le colonne in base al contenuto.
   - Restituisce il percorso completo del file generato.

3. export_filtered_excel(filters: dict | None = None) -> Path
   Funzione di alto livello che combina query + generazione.
   - Recupera i dati con query_records()
   - Genera l’Excel con generate_excel()
   - Restituisce il Path del file esportato.

Cartella di output:
-------------------
I file vengono salvati nella directory:
    magecoshipping/exports/
La cartella viene creata automaticamente se non esiste.

Note progettuali:
-----------------
- Tutte le funzioni sono indipendenti dal contesto Flask.
- I percorsi vengono risolti dinamicamente via pathlib per garantire
  compatibilità tra sistemi operativi (Windows, macOS, Linux).
- L’uso del timestamp nel nome file evita conflitti in caso di
  esportazioni simultanee.

"""