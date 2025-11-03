import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from magecoshipping.processor.processor import is_supported, process_batch_files

class StableFileHandler(FileSystemEventHandler):
    """
    Handler watchdog: raccoglie file e attende che siano tutti stabili prima di processarli in batch.
    """
    def __init__(self, folder: Path, on_batch_ready, stable_seconds: float = 3.0, batch_timeout: float = 5.0):
        super().__init__()
        self.folder = Path(folder)
        self.on_batch_ready = on_batch_ready
        self.stable_seconds = stable_seconds
        self.batch_timeout = batch_timeout  # Tempo di attesa per altri file prima di processare il batch
        self._stop = False
        self._pending_files = set()  # File rilevati ma non ancora stabili
        self._stable_files = set()   # File stabili pronti per il batch
        self._lock = threading.Lock()
        self._batch_timer = None

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if is_supported(path):
            with self._lock:
                self._pending_files.add(path)
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
                with self._lock:
                    self._pending_files.discard(path)
                return  # il file è stato rimosso

            if size == last_size:
                stable_time += 1
                if stable_time >= self.stable_seconds:
                    print(f"📦 File stabile: {path.name}")
                    self._mark_file_stable(path)
                    return
            else:
                stable_time = 0
                last_size = size

            time.sleep(1.0)

    def _mark_file_stable(self, path: Path):
        """Marca un file come stabile e avvia/resetta il timer del batch."""
        with self._lock:
            self._pending_files.discard(path)
            self._stable_files.add(path)

            # Cancella il timer precedente e avviane uno nuovo
            if self._batch_timer:
                self._batch_timer.cancel()

            # Avvia un timer: se non arrivano altri file entro batch_timeout, processa il batch
            self._batch_timer = threading.Timer(self.batch_timeout, self._process_batch)
            self._batch_timer.start()

    def _process_batch(self):
        """Processa tutti i file stabili raccolti."""
        with self._lock:
            if not self._stable_files:
                return

            files_to_process = list(self._stable_files)
            self._stable_files.clear()
            self._batch_timer = None

        print(f"\n🎯 Processamento batch: {len(files_to_process)} file(s)")
        self.on_batch_ready(files_to_process)

    def add_initial_file(self, path: Path):
        """Aggiunge un file trovato all'avvio alla lista dei file da processare."""
        with self._lock:
            self._pending_files.add(path)
        # Lancia un thread per attendere che sia stabile
        t = threading.Thread(target=self._wait_until_stable, args=(path,), daemon=True)
        t.start()

    def stop(self):
        self._stop = True
        with self._lock:
            if self._batch_timer:
                self._batch_timer.cancel()


class FolderWatcher:
    """
    Gestisce l'osservazione di una cartella e il trigger dell'elaborazione file in modalità batch.
    """
    def __init__(self, folder: str, on_stable_file=None, stable_seconds: float = 3.0, batch_timeout: float = 5.0):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        # Usa on_batch_ready invece di on_stable_file
        self.event_handler = StableFileHandler(
            self.folder,
            on_batch_ready=on_stable_file or self._on_batch_ready,
            stable_seconds=stable_seconds,
            batch_timeout=batch_timeout
        )
        self.observer = Observer()

    def _on_batch_ready(self, file_paths: list[Path]):
        """Callback chiamata quando un batch di file è pronto per essere processato."""
        print(f"👀 Batch di {len(file_paths)} file(s) pronto")
        process_batch_files(file_paths)

    def start(self):
        print(f"🛰️ Watcher attivo su: {self.folder}")

        # 1️⃣ Trova tutti i file già presenti
        initial_files = []
        for file in self.folder.glob("*.xml"):
            if is_supported(file):
                print(f"📁 File pre-esistente trovato: {file.name}")
                initial_files.append(file)

        # Aggiungi i file iniziali all'handler per la stabilizzazione
        for file in initial_files:
            self.event_handler.add_initial_file(file)

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
