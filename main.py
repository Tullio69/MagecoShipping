import os
from pathlib import Path
from magecoshipping.db.schema import init_db
from magecoshipping.system.tray_app import run_tray

# ================================
# MagecoShipping - Entry Point
# ================================

def ensure_directories():
    """
    Crea le cartelle operative se non esistono.
    """
    base_dir = Path(__file__).parent
    folders = [
        base_dir / "watched",
        base_dir / "processed",
        base_dir / "errors",
        base_dir / "logs",
        base_dir / "magecoshipping" / "db"
    ]
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)


def main():
    """
    Avvia MagecoShipping come tray app.
    """
    print("🚀 Avvio MagecoShipping...")

    # 1️⃣ Crea le cartelle base
    ensure_directories()

    # 2️⃣ Inizializza il database SQLite
    init_db()

    # 3️⃣ Avvia la tray app (icona e menu)
    run_tray()


if __name__ == "__main__":
    main()
