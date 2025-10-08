from flask import Flask, render_template, request
from threading import Thread
import webbrowser
from pathlib import Path
from magecoshipping.utils.db_utils import insert_document
from magecoshipping.utils.fs_ops import move_with_retry

app = Flask(__name__)

@app.route("/review", methods=["GET", "POST"])
def review():
    data = app.config.get("current_data", {})

    if request.method == "POST":
        action = request.form.get("action")

        original_path = Path(data.get("original_path"))
        processed_dir = Path(__file__).resolve().parents[2] / "processed"
        errors_dir = Path(__file__).resolve().parents[2] / "errors"

        if action == "confirm":
            # ✅ conferma → scrive su DB → sposta file in processed
            data["status"] = "validated"
            insert_document(data)
            move_with_retry(original_path, processed_dir)
            message = "✅ Dati convalidati e salvati con successo."

        elif action == "correct":
            # 📝 correggi → prendi valori aggiornati dal form
            data.update(request.form)
            data["status"] = "validated"
            insert_document(data)
            move_with_retry(original_path, processed_dir)
            message = "✏️ Dati corretti e salvati con successo."

        elif action == "reject":
            # ❌ rifiuta → nessun salvataggio → sposta in errors
            move_with_retry(original_path, errors_dir)
            message = "🚫 Documento rifiutato e spostato in errors."

        else:
            message = "⚠️ Nessuna azione eseguita."

        return render_template("result.html", message=message)

    return render_template("confirm.html", data=data)

def _run_server():
    app.run(port=5001, debug=False)

def start_review_server(data_dict):
    app.config["current_data"] = data_dict
    Thread(target=_run_server, daemon=True).start()
    webbrowser.open("http://localhost:5001/review")
