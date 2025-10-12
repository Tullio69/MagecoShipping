from flask import Flask, render_template, request
from threading import Thread
import webbrowser
from pathlib import Path
from magecoshipping.utils.db_utils import insert_document
from magecoshipping.utils.fs_ops import move_with_retry

app = Flask(__name__)

@app.route("/review", methods=["GET", "POST"])
def review():
    """
    Mostra il form di revisione e gestisce le azioni di conferma / correzione / rifiuto.
    """
    data = app.config.get("current_data", {})

    if request.method == "POST":
        action = request.form.get("action")
        print("[DEBUG] Dati ricevuti dal form:", dict(request.form))  # utile per debug

        # Percorsi cartelle di destinazione
        original_path = Path(data.get("original_path"))
        processed_dir = Path(__file__).resolve().parents[2] / "processed"
        errors_dir = Path(__file__).resolve().parents[2] / "errors"

        if action == "confirm":
            # ✅ CONVALIDA: salva su DB e sposta in processed
            try:
                data["status"] = "validated"
                insert_document(data)
                move_with_retry(original_path, processed_dir)
                msg = "✅ Documento convalidato e salvato nel database."
            except Exception as e:
                msg = f"❌ Errore nel salvataggio: {e}"

        elif action == "correct":
            # ✏️ CORREGGI: aggiorna i valori dal form
            try:
                for key in data.keys():
                    if key in request.form:
                        data[key] = request.form[key]
                data["status"] = "validated"
                insert_document(data)
                move_with_retry(original_path, processed_dir)
                msg = "✏️ Dati corretti e salvati con successo."
            except Exception as e:
                msg = f"❌ Errore durante la correzione: {e}"

        elif action == "reject":
            # ❌ RIFIUTA: sposta in errors
            try:
                move_with_retry(original_path, errors_dir)
                msg = "🚫 Documento rifiutato e spostato in errors."
            except Exception as e:
                msg = f"❌ Errore durante il rifiuto: {e}"

        else:
            msg = "⚠️ Nessuna azione riconosciuta."

        return render_template("result.html", message=msg)

    return render_template("confirm.html", data=data)

def _run_server():
    app.run(port=5001, debug=False)

def start_review_server(data_dict):
    app.config["current_data"] = data_dict
    thread = Thread(target=_run_server, daemon=True)
    thread.start()
    webbrowser.open("http://localhost:5001/review")
