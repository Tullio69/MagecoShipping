import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class StableFileHandler(FileSystemEventHandler):
    def __init__(self, folder: Path, on_stable_file, stable_seconds: float = 3.0):
        super().__init__()
        self.folder = Path(folder)
        self.on_stable_file = on_stable_file
        self.stable_seconds = stable_seconds
        self._locks = {}  # path -> last size ts
        self._stop = False
        self._paused = False  # <-- NEW

    # NEW: pausa/ripresa eventi
    def set_paused(self, value: bool):
        self._paused = value

    def on_created(self, event):
        if event.is_directory or self._paused:
            return
        p = Path(event.src_path)
        t = threading.Thread(target=self._wait_stable_and_emit, args=(p,), daemon=True)
        t.start()

    # NEW: gestisci anche modified (alcuni copy tool emettono solo questo)
    def on_modified(self, event):
        if event.is_directory or self._paused:
            return
        p = Path(event.src_path)
        t = threading.Thread(target=self._wait_stable_and_emit, args=(p,), daemon=True)
        t.start()

    # NEW: gestisci rename/move nella stessa dir
    def on_moved(self, event):
        if event.is_directory or self._paused:
            return
        p = Path(event.dest_path)
        t = threading.Thread(target=self._wait_stable_and_emit, args=(p,), daemon=True)
        t.start()

    def _wait_stable_and_emit(self, path: Path):
        last_size = -1
        same_count = 0
        while not self._stop:
            if self._paused:
                return  # in pausa non emetti nulla
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                return  # sparito
            if size == last_size:
                same_count += 1
            else:
                same_count = 0
                last_size = size
            if same_count * 0.5 >= self.stable_seconds:  # campiona ogni 0.5s
                try:
                    self.on_stable_file(path)
                except Exception as e:
                    print(f"[watcher] on_stable_file error for {path}: {e}")
                return
            time.sleep(0.5)

    def stop(self):
        self._stop = True

    # NEW: reconciliation scan per files già presenti in cartella
    def reconciliation_scan(self):
        if self._paused:
            return
        for p in self.folder.iterdir():
            if p.is_file():
                t = threading.Thread(target=self._wait_stable_and_emit, args=(p,), daemon=True)
                t.start()


class FolderWatcher:
    def __init__(self, folder: str, on_stable_file, stable_seconds: float = 3.0):
        self.folder = Path(folder)
        self.handler = StableFileHandler(self.folder, on_stable_file, stable_seconds)
        self.observer = Observer()
        self._running = False  # <-- NEW

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.handler.set_paused(False)  # <-- NEW
        self.observer.schedule(self.handler, str(self.folder), recursive=False)
        self.observer.start()
        self._running = True
        # NEW: cattura file già presenti all'avvio
        self.handler.reconciliation_scan()

    def pause(self):  # <-- NEW
        if not self._running:
            return
        self.handler.set_paused(True)
        self.observer.stop()
        self.observer.join(timeout=3)
        self._running = False

    def resume(self):  # <-- NEW
        # prima riconcilia (processa ciò che è stato aggiunto in pausa)
        self.handler.set_paused(False)
        self.handler.reconciliation_scan()
        # poi riaccendi l'observer
        self.observer = Observer()
        self.observer.schedule(self.handler, str(self.folder), recursive=False)
        self.observer.start()
        self._running = True

    def stop(self):
        self.handler.stop()
        if self._running:
            self.observer.stop()
            self.observer.join(timeout=3)
            self._running = False

    def __repr__(self):
        return f"FolderWatcher(folder={self.folder}, stable_seconds={self.handler.stable_seconds})"
