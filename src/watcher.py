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

    def on_created(self, event):
        if event.is_directory:
            return
        p = Path(event.src_path)
        # lancia un thread che aspetta che il file "si stabilizzi"
        t = threading.Thread(target=self._wait_stable_and_emit, args=(p,), daemon=True)
        t.start()

    def _wait_stable_and_emit(self, path: Path):
        last_size = -1
        same_count = 0
        # considera il file stabilizzato quando la dimensione resta uguale per N secondi
        while not self._stop:
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
                self.on_stable_file(path)
                return
            time.sleep(0.5)

    def stop(self):
        self._stop = True

class FolderWatcher:
    def __init__(self, folder: str, on_stable_file, stable_seconds: float = 3.0):
        self.folder = Path(folder)
        self.handler = StableFileHandler(self.folder, on_stable_file, stable_seconds)
        self.observer = Observer()

    def start(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        self.observer.schedule(self.handler, str(self.folder), recursive=False)
        self.observer.start()

    def stop(self):
        self.handler.stop()
        self.observer.stop()
        self.observer.join(timeout=3)

    def __repr__(self):
        return f"FolderWatcher(folder={self.folder}, stable_seconds={self.handler.stable_seconds})"
