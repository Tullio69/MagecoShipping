from flask import Flask, render_template, request, jsonify, flash, send_file, redirect, url_for
from threading import Thread, Lock
import webbrowser
from pathlib import Path
from magecoshipping.utils.db_utils import insert_document, insert_or_get_supplier
from magecoshipping.utils.fs_ops import move_with_retry
from magecoshipping.utils import excel
import re
import secrets



app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Variabili globali per gestire lo stato del server
_server_running = False
_server_lock = Lock()

@app.route("/review", methods=["GET", "POST"])
def review():
    """
    Mostra il form di revisione e gestisce conferma / correzione / rifiuto.
    Ora include flag recognized/include e controllo fornitore.
    """
    data = app.config.get("current_data", {})
    lines = data.get("lines", [])

    if request.method == "POST":
        action = request.form.get("action")
        print(f"[DEBUG] Azione ricevuta: {action}")

        # Aggiorna righe dal form
        updated_lines = []
        i = 0
        while True:
            prefix = f"line_{i}_"
            if f"{prefix}descrizione_rigo" not in request.form:
                break
            updated_lines.append({
                "descrizione_rigo": request.form.get(f"{prefix}descrizione_rigo", ""),
                "tratta": request.form.get(f"{prefix}tratta", ""),
                "targhe": request.form.get(f"{prefix}targhe", ""),
                "tipo_veicolo": request.form.get(f"{prefix}tipo_veicolo", ""),
                "quantita_fattura": float(request.form.get(f"{prefix}quantita_fattura", 1)),
                "quantita_reale": float(request.form.get(f"{prefix}quantita_reale", 1)),
                "costo": float(request.form.get(f"{prefix}costo", 0)),
                "recognized": request.form.get(f"{prefix}recognized") == "True",
                "include": f"{prefix}include" in request.form
            })
            i += 1

        data["lines"] = updated_lines

        # Percorsi
        original_path = Path(data.get("original_path"))
        processed_dir = Path(__file__).resolve().parents[2] / "processed"
        errors_dir = Path(__file__).resolve().parents[2] / "errors"

        if action in ("confirm", "correct"):
            try:
                # ✅ Controlla o crea il fornitore
                supplier_id = insert_or_get_supplier(
                    fornitore=data.get("fornitore"),
                    piva_fornitore=data.get("piva_fornitore")
                )
                data["supplier_id"] = supplier_id

                data["status"] = "validated"
                insert_document(data)
                move_with_retry(original_path, processed_dir)

                if action == "confirm":
                    msg = "✅ Documento convalidato e salvato nel database."
                else:
                    msg = "✏️ Dati corretti e salvati con successo."
            except Exception as e:
                msg = f"❌ Errore nel salvataggio: {e}"

        elif action == "reject":
            try:
                move_with_retry(original_path, errors_dir)
                msg = "🚫 Documento rifiutato e spostato in errors."
            except Exception as e:
                msg = f"❌ Errore durante il rifiuto: {e}"
        else:
            msg = "⚠️ Nessuna azione riconosciuta."

        return render_template("result.html", message=msg)

    return render_template("confirm.html", data=data, lines=lines)


@app.route("/validate_text", methods=["POST"])

def validate_text():
    """
    API AJAX per controllare se la descrizione rispetta le convenzioni MagecoShipping.
    Ritorna JSON con recognized=True/False.
    """
    descr = request.json.get("descr", "")
    tratta = bool(re.search(r"\b[A-Z]{1,3}/[A-Z]{1,3}\b", descr.upper()))
    targa = bool(re.search(r"\b[A-Z]{2}\d{2,4}[A-Z]{2}\b", descr.upper()))
    tipo = any(k in descr.lower() for k in ["autovettur", "autocarro", "furgon", "bus", "pullman", "moto"])
    recognized = tratta or targa or tipo
    return flask.jsonify({"recognized": recognized})

from magecoshipping.utils.db_utils import get_documents

@app.route("/dbview", methods=["GET"])
def dbview():
    """
    Visualizza l'elenco dei documenti dal database con filtro di ricerca.
    """
    query = request.args.get("q", "")
    try:
        documents = get_documents(query)
    except Exception as e:
        return f"<h3>Errore durante il caricamento dei dati: {e}</h3>"

    return render_template("dbview.html", docs=documents, query=query)



from flask import render_template, request, flash, redirect, url_for
import platform, subprocess, os
from magecoshipping.utils.db_utils import get_documents
from magecoshipping.utils import excel

@app.route("/export", methods=["GET", "POST"])
def export_page():
    query = request.args.get("q", "")
    anno = request.args.get("anno", "")
    cliente = request.args.get("cliente", "")
    status = request.args.get("status", "validated")

    try:
        documents = get_documents(query, status_filter=status)
        if anno:
            documents = [d for d in documents if d.get("data_doc", "").startswith(anno)]
        if cliente:
            documents = [d for d in documents if cliente.lower() in (d.get("cliente") or "").lower()]
    except Exception as e:
        flash(f"❌ Errore caricamento documenti: {e}", "error")
        documents = []

    anni = sorted({str(d["data_doc"])[:4] for d in documents if d.get("data_doc")})
    clienti = sorted({d["cliente"] for d in documents if d.get("cliente")})

    if request.method == "POST":
        selected_ids = request.form.getlist("selected_ids")
        if not selected_ids:
            flash("⚠️ Nessun documento selezionato per l’esportazione.", "error")
            return redirect(url_for("export_page"))

        try:
            filters = {"ids": [int(i) for i in selected_ids]}
            excel_path = excel.export_filtered_excel(filters)
            flash(f"✅ File generato: {excel_path.name}", "success")
            return redirect(url_for("export_page"))
        except Exception as e:
            flash(f"❌ Errore durante l’esportazione: {e}", "error")
            return redirect(url_for("export_page"))

    return render_template("export.html", docs=documents, query=query,
                           anno=anno, anni=anni,
                           cliente=cliente, clienti=clienti, status=status)



@app.route("/open_export_folder", methods=["POST"])
def open_export_folder():
    """
    Apre la cartella degli export nel file explorer del sistema operativo.
    Funziona su Windows, macOS e Linux.
    """
    exports_dir = Path(__file__).resolve().parents[1] / "exports"

    try:
        # Crea la cartella se non esiste
        exports_dir.mkdir(exist_ok=True)

        system = platform.system()
        if system == "Windows":
            os.startfile(exports_dir)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", exports_dir])
        else:  # Linux
            subprocess.Popen(["xdg-open", exports_dir])

        return flask.jsonify({"success": True, "message": f"Aperta cartella: {exports_dir}"}), 200
    except Exception as e:
        return flask.jsonify({"success": False, "message": str(e)}), 500


@app.route("/batch-review", methods=["GET", "POST"])
def batch_review():
    """
    Modalità batch: permette di revisionare più documenti in sequenza.
    """
    # Carica batch da app.config (non session perché non funziona con daemon thread)
    batch_documents = app.config.get("batch_documents", [])
    failed_files = app.config.get("failed_files", [])
    current_index = app.config.get("current_index", 0)

    if not batch_documents:
        return render_template("result.html", message="⚠️ Nessun batch di documenti da revisionare.")

    if request.method == "POST":
        action = request.form.get("action")

        # Navigazione
        if action == "navigate":
            direction = request.form.get("direction")
            if direction == "prev" and current_index > 0:
                current_index -= 1
            elif direction == "next" and current_index < len(batch_documents) - 1:
                current_index += 1
            app.config["current_index"] = current_index
            return redirect(url_for("batch_review"))

        # Conferma batch completo
        if action == "confirm_batch":
            app.config["batch_documents"] = []
            app.config["failed_files"] = []
            app.config["current_index"] = 0
            return render_template("result.html", message="✅ Batch completo! Tutti i documenti sono stati processati.")

        # Aggiorna righe dal form
        updated_lines = []
        i = 0
        while True:
            prefix = f"line_{i}_"
            if f"{prefix}descrizione_rigo" not in request.form:
                break
            updated_lines.append({
                "descrizione_rigo": request.form.get(f"{prefix}descrizione_rigo", ""),
                "tratta": request.form.get(f"{prefix}tratta", ""),
                "targhe": request.form.get(f"{prefix}targhe", ""),
                "tipo_veicolo": request.form.get(f"{prefix}tipo_veicolo", ""),
                "quantita_fattura": float(request.form.get(f"{prefix}quantita_fattura", 1)),
                "quantita_reale": float(request.form.get(f"{prefix}quantita_reale", 1)),
                "costo": float(request.form.get(f"{prefix}costo", 0)),
                "recognized": request.form.get(f"{prefix}recognized") == "True",
                "include": f"{prefix}include" in request.form
            })
            i += 1

        batch_documents[current_index]["lines"] = updated_lines

        # Percorsi
        original_path = Path(batch_documents[current_index].get("original_path"))
        processed_dir = Path(__file__).resolve().parents[2] / "processed"
        errors_dir = Path(__file__).resolve().parents[2] / "errors"

        if action in ("confirm", "correct"):
            try:
                # Controlla o crea il fornitore
                supplier_id = insert_or_get_supplier(
                    fornitore=batch_documents[current_index].get("fornitore"),
                    piva_fornitore=batch_documents[current_index].get("piva_fornitore")
                )
                batch_documents[current_index]["supplier_id"] = supplier_id
                batch_documents[current_index]["status"] = "validated"
                insert_document(batch_documents[current_index])
                move_with_retry(original_path, processed_dir)

                # Marca come processato
                batch_documents[current_index]["_processed"] = True
                batch_documents[current_index]["_action"] = "confirm"

            except Exception as e:
                flash(f"❌ Errore nel salvataggio: {e}", "error")

        elif action == "reject":
            try:
                move_with_retry(original_path, errors_dir)
                batch_documents[current_index]["_processed"] = True
                batch_documents[current_index]["_action"] = "reject"
            except Exception as e:
                flash(f"❌ Errore durante il rifiuto: {e}", "error")

        # Salva aggiornamenti in app.config
        app.config["batch_documents"] = batch_documents

        # Vai al prossimo documento non processato
        next_index = current_index
        for i in range(current_index + 1, len(batch_documents)):
            if not batch_documents[i].get("_processed"):
                next_index = i
                break

        if next_index != current_index:
            app.config["current_index"] = next_index

        return redirect(url_for("batch_review"))

    # GET request - mostra documento corrente
    data = batch_documents[current_index]
    lines = data.get("lines", [])

    return render_template(
        "batch_review.html",
        data=data,
        lines=lines,
        batch_documents=batch_documents,
        failed_files=failed_files,
        current_index=current_index,
        total_documents=len(batch_documents)
    )


def _run_server():
    """
    Avvia il server Flask completo con tutte le route (review, dbview, edit, ecc.)
    """
    global _server_running
    try:
        app.run(port=5001, debug=False, use_reloader=False)
    finally:
        with _server_lock:
            _server_running = False


def start_batch_review_server(batch_documents, failed_files=None):
    """
    Avvia il server Flask in modalità batch-review con più documenti.

    Args:
        batch_documents: Lista di dizionari contenenti i dati dei documenti
        failed_files: Lista di file che hanno avuto errori di parsing (opzionale)
    """
    global _server_running

    # Prepara i dati della sessione (usando app.config per simulare session)
    app.config["batch_documents"] = batch_documents
    app.config["failed_files"] = failed_files or []
    app.config["current_index"] = 0

    # Avvia il server se non è già in esecuzione
    with _server_lock:
        if not _server_running:
            _server_running = True
            from threading import Thread
            thread = Thread(target=_run_server, daemon=True)
            thread.start()
            print("🌐 Server Flask avviato su porta 5001 (modalità batch)")

            import time
            time.sleep(0.5)
        else:
            print("🌐 Server Flask già in esecuzione, modalità batch attivata...")

    # Apri il browser sulla pagina batch-review
    import webbrowser
    webbrowser.open("http://localhost:5001/batch-review")


def start_review_server(data_dict=None, open_page="review"):
    """
    Avvia il server Flask e apre la pagina desiderata nel browser.
    Se il server è già in esecuzione, aggiorna solo i dati e apre una nuova scheda.

    Esempi:
        start_review_server(data_dict)             -> apre /review
        start_review_server(open_page="dbview")    -> apre /dbview
    """
    global _server_running

    if data_dict:
        app.config["current_data"] = data_dict

    # Controlla se il server è già in esecuzione
    with _server_lock:
        server_already_running = _server_running

        if not _server_running:
            # Avvia il server solo se non è già in esecuzione
            _server_running = True
            from threading import Thread
            thread = Thread(target=_run_server, daemon=True)
            thread.start()
            print("🌐 Server Flask avviato su porta 5001")

            # Attende mezzo secondo per consentire l'avvio del server
            import time
            time.sleep(0.5)
        else:
            print("🌐 Server Flask già in esecuzione, aggiornamento dati...")

    # Apri il browser solo se ci sono nuovi dati da visualizzare
    if data_dict:
        import webbrowser
        webbrowser.open(f"http://localhost:5001/{open_page}")


from magecoshipping.utils.db_utils import get_documents
import sqlite3
from magecoshipping.db.schema import DB_PATH
@app.route("/dbview/edit/<int:doc_id>", methods=["GET", "POST"])
def edit_document(doc_id):
    """
    Visualizza e modifica un documento con tutte le sue righe.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Carica il documento e le righe
    cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
    doc = cur.fetchone()
    cur.execute("SELECT * FROM document_lines WHERE document_id = ?", (doc_id,))
    lines = [dict(r) for r in cur.fetchall()]

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_doc":
            # Aggiorna intestazione documento
            cur.execute("""
                UPDATE documents
                SET cliente=?, piva_cliente=?, fornitore=?, piva_fornitore=?, num_doc=?, data_doc=?, totale_doc=?, status=?
                WHERE id=?
            """, (
                request.form["cliente"], request.form["piva_cliente"],
                request.form["fornitore"], request.form["piva_fornitore"],
                request.form["num_doc"], request.form["data_doc"],
                request.form["totale_doc"], request.form["status"], doc_id
            ))
            conn.commit()
            msg = "✅ Documento aggiornato con successo."

        elif action.startswith("update_line_"):
            # Aggiorna singola riga
            line_id = int(action.split("_")[-1])
            cur.execute("""
                UPDATE document_lines
                SET descrizione_rigo=?, tratta=?, targhe=?, tipo_veicolo=?, quantita_fattura=?, quantita_reale=?, costo=?, recognized=?, include=?
                WHERE id=?
            """, (
                request.form[f"descrizione_rigo_{line_id}"],
                request.form[f"tratta_{line_id}"],
                request.form[f"targhe_{line_id}"],
                request.form[f"tipo_veicolo_{line_id}"],
                float(request.form[f"quantita_fattura_{line_id}"] or 1),
                float(request.form[f"quantita_reale_{line_id}"] or 1),
                float(request.form[f"costo_{line_id}"] or 0),
                int("recognized_" + str(line_id) in request.form),
                int("include_" + str(line_id) in request.form),
                line_id
            ))
            conn.commit()
            msg = f"✏️ Riga {line_id} aggiornata con successo."

        elif action == "delete_doc":
            # Elimina documento e righe
            cur.execute("DELETE FROM document_lines WHERE document_id = ?", (doc_id,))
            cur.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
            conn.close()
            return render_template("result.html", message="🗑️ Documento eliminato definitivamente.")

        # Ricarica dati aggiornati
        cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cur.fetchone()
        cur.execute("SELECT * FROM document_lines WHERE document_id = ?", (doc_id,))
        lines = [dict(r) for r in cur.fetchall()]

        return render_template("edit_doc.html", doc=doc, lines=lines, msg=msg)

    conn.close()
    return render_template("edit_doc.html", doc=doc, lines=lines)
