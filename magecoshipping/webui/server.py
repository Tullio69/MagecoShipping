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


from flask import redirect, url_for

@app.route("/export", methods=["GET", "POST"])
def export_page():
    """
    Pagina di esportazione in Excel dei documenti registrati.
    - GET: mostra elenco documenti e form di filtro
    - POST: genera il file Excel e apre la cartella Export (senza download browser)
    """
    import platform
    import subprocess
    import os
    from flask import redirect, url_for

    query = request.args.get("q", "")
    status = request.args.get("status", "")

    from magecoshipping.utils.db_utils import get_documents
    documents = get_documents(query)

    if request.method == "POST":
        selected_ids = request.form.getlist("selected_ids")

        # Se non è selezionato nulla, avvisa e non esporta
        if not selected_ids:
            flash("⚠️ Nessun documento selezionato per l’esportazione.", "error")
            return redirect(url_for("export_page"))

        filters = {"ids": selected_ids}
        try:
            #Crea la cartella exports
            excel_path = excel.export_filtered_excel(filters)
            flash(f"✅ File generato correttamente: {excel_path.name}", "success")

            # 🔹 Apre la cartella Export in base al sistema operativo
            exports_dir = excel_path.parent
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", exports_dir])
            elif system == "Windows":
                os.startfile(str(exports_dir))
            else:  # Linux
                subprocess.Popen(["xdg-open", exports_dir])

            # 🔹 Ritorna alla pagina export con il messaggio di successo
            return redirect(url_for("export_page"))

        except Exception as e:
            flash(f"❌ Errore durante la generazione: {e}", "error")
            return redirect(url_for("export_page"))

    # 🔹 GET: mostra la pagina
    return render_template("export.html", docs=documents, query=query, status=status)

import os
import platform
import subprocess
from flask import jsonify

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

        return jsonify({"success": True, "message": f"Aperta cartella: {exports_dir}"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


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
