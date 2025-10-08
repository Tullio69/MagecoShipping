import os
import sys
import subprocess
from pathlib import Path

def run_cmd(cmd, cwd=None):
    """Esegue un comando e mostra output in tempo reale."""
    print(f"\n> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ Errore durante l'esecuzione: {' '.join(cmd)}")
        sys.exit(result.returncode)

def main():
    project_root = Path(__file__).parent.resolve()
    venv_dir = project_root / ".venv"
    requirements = project_root / "requirements.txt"

    print("🚀 Setup ambiente MagecoShipping\n")

    # 1️⃣ Crea l’ambiente virtuale se non esiste
    if not venv_dir.exists():
        print("📦 Creazione ambiente virtuale...")
        run_cmd([sys.executable, "-m", "venv", str(venv_dir)])
    else:
        print("✅ Ambiente virtuale già esistente.")

    # 2️⃣ Attiva pip dentro .venv
    pip_exe = venv_dir / "Scripts" / "pip.exe" if os.name == "nt" else venv_dir / "bin" / "pip"

    # 3️⃣ Aggiorna pip
    print("\n🔁 Aggiornamento pip...")
    run_cmd([str(pip_exe), "install", "--upgrade", "pip"])

    # 4️⃣ Installa dipendenze
    if requirements.exists():
        print("\n📚 Installazione pacchetti da requirements.txt...")
        run_cmd([str(pip_exe), "install", "-r", str(requirements)])
    else:
        print("⚠️ File requirements.txt non trovato — nessun pacchetto installato.")

    # 5️⃣ Fine
    print("\n✅ Setup completato!")
    print("Per attivare l'ambiente:")
    if os.name == "nt":
        print("  .venv\\Scripts\\activate")
    else:
        print("  source .venv/bin/activate")

if __name__ == "__main__":
    main()
