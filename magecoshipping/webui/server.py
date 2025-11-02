from flask import Flask, render_template, request, jsonify, flash, send_file
from threading import Thread
import webbrowser
from pathlib import Path
from magecoshipping.utils.db_utils import insert_document, insert_or_get_supplier
from magecoshipping.utils.fs_ops import move_with_retry
from magecoshipping.utils import excel 
import re
import secrets



app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

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


@app.route("/batch-review", methods=["GET", "POST"])
def batch_review():
    """
    Gestisce la review di un batch di documenti multipli.
    Permette navigazione tra documenti e conferma/correzione/rifiuto di ciascuno.
    """
    from magecoshipping.utils.db_utils import create_batch, insert_document, insert_or_get_supplier
    from datetime import datetime

    batch_documents = app.config.get("batch_documents", [])
    batch_failed_files = app.config.get("batch_failed_files", [])

    if not batch_documents:
        return render_template("result.html", message="⚠️ Nessun documento nel batch.")

    current_index = app.config.get("batch_current_index", 0)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "navigate":
            # Navigazione tra documenti
            direction = request.form.get("direction")
            if direction == "next" and current_index < len(batch_documents) - 1:
                current_index += 1
            elif direction == "prev" and current_index > 0:
                current_index -= 1
            app.config["batch_current_index"] = current_index

        elif action in ("confirm", "correct", "reject"):
            # Aggiorna il documento corrente con i dati dal form
            current_doc = batch_documents[current_index]

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

            current_doc["lines"] = updated_lines

            # Marca il documento come processato
            current_doc["_processed"] = True
            current_doc["_action"] = action

            # Se è l'ultimo documento o l'utente ha cliccato "Conferma batch"
            if action == "confirm_batch" or all(doc.get("_processed") for doc in batch_documents):
                # Crea il batch nel database
                batch_name = f"Batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                batch_id = create_batch(batch_name, len(batch_documents))

                # Processa tutti i documenti
                processed_dir = Path(__file__).resolve().parents[2] / "processed"
                errors_dir = Path(__file__).resolve().parents[2] / "errors"

                messages = []
                for doc in batch_documents:
                    doc_action = doc.get("_action", "confirm")
                    original_path = Path(doc.get("original_path"))

                    if doc_action in ("confirm", "correct"):
                        try:
                            supplier_id = insert_or_get_supplier(
                                fornitore=doc.get("fornitore"),
                                piva_fornitore=doc.get("piva_fornitore")
                            )
                            doc["supplier_id"] = supplier_id
                            doc["status"] = "validated"

                            # Inserisci documento con batch_id
                            insert_document(doc, batch_id=batch_id)
                            move_with_retry(original_path, processed_dir)
                            messages.append(f"✅ {doc['file_name']}: Validato")
                        except Exception as e:
                            messages.append(f"❌ {doc['file_name']}: Errore - {e}")

                    elif doc_action == "reject":
                        try:
                            move_with_retry(original_path, errors_dir)
                            messages.append(f"🚫 {doc['file_name']}: Rifiutato")
                        except Exception as e:
                            messages.append(f"❌ {doc['file_name']}: Errore - {e}")

                # Mostra risultato finale
                result_msg = f"<h3>📦 Batch '{batch_name}' completato</h3><ul>"
                for msg in messages:
                    result_msg += f"<li>{msg}</li>"
                result_msg += "</ul>"

                if batch_failed_files:
                    result_msg += "<h4>⚠️ File con errori:</h4><ul>"
                    for file_path, error in batch_failed_files:
                        result_msg += f"<li>{Path(file_path).name}: {error}</li>"
                    result_msg += "</ul>"

                # Pulisci la configurazione del batch
                app.config.pop("batch_documents", None)
                app.config.pop("batch_failed_files", None)
                app.config.pop("batch_current_index", None)

                return render_template("result.html", message=result_msg)

            # Naviga al prossimo documento non processato
            next_index = current_index
            for i in range(current_index + 1, len(batch_documents)):
                if not batch_documents[i].get("_processed"):
                    next_index = i
                    break
            else:
                # Se tutti i documenti successivi sono processati, cerca indietro
                for i in range(current_index):
                    if not batch_documents[i].get("_processed"):
                        next_index = i
                        break

            current_index = next_index
            app.config["batch_current_index"] = current_index

    # Prepara i dati per il template
    current_doc = batch_documents[current_index]
    return render_template("batch_review.html",
                          data=current_doc,
                          lines=current_doc.get("lines", []),
                          current_index=current_index,
                          total_documents=len(batch_documents),
                          failed_files=batch_failed_files,
                          batch_documents=batch_documents)


@app.route("/validate_text", methods=["POST"])
def validate_text():
    """
    API AJAX per controllare se la descrizione rispetta le convenzioni MagecoShipping.
    Ritorna JSON con recognized=True/False.
    """
    descr = request.json.get("descr", "")
    tratta = bool(re.search(r"\b[A-Z]{1,3}/[A-Z]{1,3}\b", descr.upper()))
    targa = bool(re.search(r"\b[A-Z]{2}\d{3,4}[A-Z]{2}\b", descr.upper()))
    tipo = any(k in descr.lower() for k in ["autovettur", "autocarro", "furgon", "bus", "pullman", "moto"])
    recognized = tratta or targa or tipo
    return jsonify({"recognized": recognized})

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


def _run_server():
    """
    Avvia il server Flask completo con tutte le route (review, dbview, edit, ecc.)
    """
    app.run(port=5001, debug=False, use_reloader=False)


def start_review_server(data_dict=None, open_page="review"):
    """
    Avvia il server Flask e apre la pagina desiderata nel browser.

    Esempi:
        start_review_server(data_dict)             -> apre /review
        start_review_server(open_page="dbview")    -> apre /dbview
    """
    if data_dict:
        app.config["current_data"] = data_dict

    from threading import Thread
    thread = Thread(target=_run_server, daemon=True)
    thread.start()

    # Attende mezzo secondo per consentire l'avvio del server
    import time
    time.sleep(0.5)

    import webbrowser
    webbrowser.open(f"http://localhost:5001/{open_page}")


def start_batch_review_server(parsed_documents, failed_files=None):
    """
    Avvia il server Flask per la batch review di più documenti.

    Args:
        parsed_documents: Lista di dizionari contenenti i dati parsati di ogni documento
        failed_files: Lista opzionale di tuple (path, error) per file che non sono stati parsati correttamente
    """
    app.config["batch_documents"] = parsed_documents
    app.config["batch_failed_files"] = failed_files or []
    app.config["batch_current_index"] = 0

    from threading import Thread
    thread = Thread(target=_run_server, daemon=True)
    thread.start()

    # Attende mezzo secondo per consentire l'avvio del server
    import time
    time.sleep(0.5)

    import webbrowser
    webbrowser.open(f"http://localhost:5001/batch-review")


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
