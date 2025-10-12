import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from magecoshipping.processor.processor import is_supported, process_file

class StableFileHandler(FileSystemEventHandler):
    """
    Handler watchdog: attende che il file sia stabile prima di processarlo.
    """
    def __init__(self, folder: Path, on_stable_file, stable_seconds: float = 3.0):
        super().__init__()
        self.folder = Path(folder)
        self.on_stable_file = on_stable_file
        self.stable_seconds = stable_seconds
        self._stop = False

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if is_supported(path):
            # Lancia un thread per attendere che il file sia stabile
            t = threading.Thread(target=self._wait_until_stable, args=(path,), daemon=True)
            t.start()

    def _wait_until_stable(self, path: Path):
        """
        Attende che il file non cambi più dimensione per N secondi consecutivi.
        """
        last_size = -1
        stable_time = 0.0

        while not self._stop:
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                return  # il file è stato rimosso

            if size == last_size:
                stable_time += 1
                if stable_time >= self.stable_seconds:
                    print(f"📦 File stabile: {path}")
                    self.on_stable_file(path)
                    return
            else:
                stable_time = 0
                last_size = size

            time.sleep(1.0)

    def stop(self):
        self._stop = True


class FolderWatcher:
    """
    Gestisce l’osservazione di una cartella e il trigger dell’elaborazione file.
    """
    def __init__(self, folder: str, on_stable_file=None, stable_seconds: float = 3.0):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.event_handler = StableFileHandler(self.folder, on_stable_file or self._on_file_ready, stable_seconds)
        self.observer = Observer()

    def _on_file_ready(self, path: Path):
        print(f"👀 Nuovo file rilevato: {path}")
        process_file(path)

    def start(self):
        print(f"🛰️ Watcher attivo su: {self.folder}")

        # 1️⃣ Elabora subito i file già presenti
        for file in self.folder.glob("*.xml"):
            if is_supported(file):
                print(f"📁 File pre-esistente trovato: {file}")
                threading.Thread(target=self.event_handler.on_stable_file, args=(file,), daemon=True).start()

        # 2️⃣ Avvia l'osservatore in tempo reale
        self.observer.schedule(self.event_handler, str(self.folder), recursive=False)
        self.observer.start()

    def stop(self):
        print("🛑 Watcher fermato")
        self.event_handler.stop()
        self.observer.stop()
        self.observer.join()


def start_watcher():
    """
    Funzione di utilità per avviare il watcher in un thread separato (richiamata da tray_app).
    """
    watch_folder = Path(__file__).resolve().parents[2] / "watched"
    watcher = FolderWatcher(str(watch_folder))
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
