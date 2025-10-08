
import ctypes
import os
from pathlib import Path
from PIL import Image
import pystray
import tkinter as tk
from tkinter import filedialog
import sys

from magecoshipping.watcher.watcher import FolderWatcher
from magecoshipping.utils.settings import load_settings, save_settings
# aggiungi questi import

import threading
from magecoshipping.utils.modal import show_modal
from magecoshipping.utils.fs_ops import move_with_retry, write_reason_json
from magecoshipping.processor.processor import is_supported, parse_file

APP_NAME = "Tray Watch Demo"
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# ---- STATO APP ----
# Carica le impostazioni PRIMA di usarle
settings = load_settings()
WATCH_PATH = Path(settings["watch_path"])
PROCESSED_DIR = Path(settings["processed_path"])
FAILED_DIR = Path(settings["failed_path"])


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative

ICON_PATH = Path(__file__).resolve().parents[2] / "assets" / "icons" / "icon.png"


# ---- MODALE NATIVO (MessageBox) ----
MB_OK = 0x00000000
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
MB_TASKMODAL = 0x00002000

def show_modal_win32(title="Avviso", msg="Operazione completata ✅"):
    flags = MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST | MB_TASKMODAL
    ctypes.windll.user32.MessageBoxW(None, msg, title, flags)

# ---- STATO WATCHER ----
paused = False
watcher: FolderWatcher | None = None
icon: pystray.Icon | None = None




# ---- CALLBACK quando un file è stabile nella cartella ----
from magecoshipping.processor.processor import is_supported, process_file

def on_file_ready(path: Path):
    """
    Callback chiamata quando un file stabile viene trovato nella cartella osservata.
    Esegue il parsing e apre la revisione WebUI per conferma / correzione / rifiuto.
    """
    if paused:
        return

    # 1️⃣ Verifica che sia un XML supportato
    if not is_supported(path):
        return

    # 2️⃣ Avvia il processo di parsing + WebUI di revisione
    try:
        print(f"📄 File stabile trovato: {path}")
        process_file(path)
    except Exception as e:
        show_modal("Errore di elaborazione ❌", f"Si è verificato un errore durante l'elaborazione del file:\n\n{path}\n\nDettagli: {e}")


# ---- HANDLERS MENU ----
def on_show_modal(icon_, item):
    # Mostra un esempio manuale
    msg = "Questo è un avviso personalizzato.\nTesto su più righe, sempre davanti."
    # Apri la cartella attuale monitorata
    threading.Thread(target=show_modal, args=("Demo Tray", msg, str(WATCH_PATH)), daemon=True).start()

def on_open_folder(icon_, item):
    os.startfile(str(WATCH_PATH))

def _restart_watcher(new_path: Path):
    global watcher, WATCH_PATH, settings
    # stop watcher attuale
    if watcher:
        watcher.stop()
        watcher = None
    WATCH_PATH = new_path
    settings["watch_path"] = str(WATCH_PATH)
    save_settings(settings)
    # start nuovo watcher
    _start_watcher()
    # aggiorna menu (mostra nuova cartella e ripristina stato)
    icon.menu = build_menu()
    icon.update_menu()
    # feedback
    show_modal_win32("Cartella aggiornata", f"Ora monitoro:\n{WATCH_PATH}")

def on_choose_folder(icon_, item):
    # Apri il selettore in un thread per non bloccare la tray
    def _choose():
        # Tk headless + filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        sel = filedialog.askdirectory(initialdir=str(WATCH_PATH), title="Seleziona cartella da monitorare")
        root.destroy()
        if sel:
            _restart_watcher(Path(sel))
    threading.Thread(target=_choose, daemon=True).start()

def on_toggle_pause(icon_, item):
    global paused
    paused = not paused
    icon.menu = build_menu()
    icon.update_menu()

def on_exit(icon_, item):
    try:
        if watcher:
            watcher.stop()
    finally:
        icon_.stop()

# ---- MENU DINAMICO ----
def _short(p: Path, max_len=45):
    s = str(p)
    return s if len(s) <= max_len else "…" + s[-max_len:]

def build_menu():
    state = "Riprendi monitoraggio" if paused else "Pausa monitoraggio"
    return pystray.Menu(
        pystray.MenuItem(f"Cartella: {_short(WATCH_PATH)}", None, enabled=False),
        pystray.MenuItem("Seleziona cartella…", on_choose_folder),
        pystray.MenuItem("Apri cartella", on_open_folder),
        pystray.MenuItem(state, on_toggle_pause),
        pystray.MenuItem("Mostra avviso", on_show_modal),
        pystray.MenuItem("Esci", on_exit)
    )

def create_icon():
    image = Image.open(ICON_PATH)
    return pystray.Icon(APP_NAME, image, APP_NAME, build_menu())

def _start_watcher():
    global watcher
    watcher = FolderWatcher(str(WATCH_PATH), on_stable_file=on_file_ready, stable_seconds=3.0)
    watcher.start()

# ---- MAIN ----
def run_tray():
    """
    Avvia MagecoShipping come Tray App.
    """
    global icon

    WATCH_PATH.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FAILED_DIR.mkdir(parents=True, exist_ok=True)

    _start_watcher()
    icon = create_icon()
    icon.run()
