from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Flask è attivo e risponde correttamente!"

if __name__ == "__main__":
    print("🌐 Avvio test Flask su http://127.0.0.1:5001/dbview ...")
    app.run(host="127.0.0.1", port=5001, debug=True)
