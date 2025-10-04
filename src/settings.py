from pathlib import Path
import json, os

APP_DIR = Path(os.getenv("APPDATA", Path.home())) / "TrayWatchDemo"
APP_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULTS = {
    "watch_path": str((Path.home() / "TrayWatchDemo" / "watched").resolve())  # cartella utente di default
}

def load_settings():
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return {**DEFAULTS, **data}
        except Exception:
            return DEFAULTS.copy()
    return DEFAULTS.copy()

def save_settings(data: dict):
    SETTINGS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
