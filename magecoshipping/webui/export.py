from flask import Blueprint, render_template, request, jsonify
from magecoshipping.utils.db_utils import get_connection
from magecoshipping.utils.excel import export_to_excel

bp = Blueprint("export", __name__, url_prefix="/export")


@bp.route("/", methods=["GET"])
def export_page():
    """Mostra la pagina web con selezione cliente e anno reale dal DB."""
    conn = get_connection()
    cur = conn.cursor()

    # Elenco clienti reali
    cur.execute("SELECT DISTINCT cliente FROM documents WHERE cliente IS NOT NULL AND TRIM(cliente) != '' ORDER BY cliente ASC")
    clienti = [row["cliente"] for row in cur.fetchall()]

    # Elenco anni reali (estratti dal campo data_doc)
    cur.execute("SELECT DISTINCT strftime('%Y', data_doc) AS anno FROM documents ORDER BY anno DESC")
    anni = [row["anno"] for row in cur.fetchall() if row["anno"]]

    conn.close()

    return render_template("export.html", clienti=clienti, anni=anni)


@bp.route("/generate", methods=["POST"])
def generate_export():
    """Genera l’export Excel filtrato per cliente e anno."""
    cliente = request.form.get("cliente", "").strip()
    anno = request.form.get("anno", "").strip()

    if not cliente or not anno:
        return jsonify({"success": False, "error": "Cliente e anno sono obbligatori."}), 400

    try:
        path = export_to_excel(cliente=cliente, anno=int(anno))
        return jsonify({"success": True, "message": f"Export completato per {cliente} - {anno}.", "path": str(path)})
    except Exception as e:
        return jsonify({"success": False, "error": f"Errore durante l'export: {e}"}), 500
