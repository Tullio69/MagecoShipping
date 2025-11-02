import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from magecoshipping.processor.processor import is_supported, process_file, process_batch
from collections import deque
from datetime import datetime, timedelta

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


class BatchCollector:
    """
    Raccoglie file multipli e li processa come batch dopo un timeout.
    """
    def __init__(self, batch_timeout: float = 10.0):
        self.batch_timeout = batch_timeout
        self.pending_files = []
        self.last_file_time = None
        self.lock = threading.Lock()
        self.batch_thread = None
        self.active = True

    def add_file(self, path: Path):
        """Aggiunge un file al batch e resetta il timeout."""
        with self.lock:
            if path not in self.pending_files:
                self.pending_files.append(path)
                self.last_file_time = datetime.now()
                print(f"📥 File aggiunto al batch: {path.name} (totale: {len(self.pending_files)})")

            # Avvia il thread di monitoraggio se non è attivo
            if self.batch_thread is None or not self.batch_thread.is_alive():
                self.batch_thread = threading.Thread(target=self._monitor_batch, daemon=True)
                self.batch_thread.start()

    def _monitor_batch(self):
        """Monitora il batch e processa quando scade il timeout."""
        while self.active:
            with self.lock:
                if not self.pending_files:
                    return

                time_since_last = (datetime.now() - self.last_file_time).total_seconds()

                if time_since_last >= self.batch_timeout:
                    # Timeout scaduto, processa il batch
                    files_to_process = self.pending_files.copy()
                    self.pending_files.clear()

                    print(f"\n⏰ Timeout batch scaduto. Processamento di {len(files_to_process)} file...")

                    # Rilascia il lock prima di processare
                    threading.Thread(target=self._process_batch, args=(files_to_process,), daemon=True).start()
                    return

            time.sleep(1.0)

    def _process_batch(self, files: list):
        """Processa un batch di file."""
        if len(files) == 1:
            # Se c'è un solo file, usa il processo singolo
            print(f"📄 Processamento file singolo: {files[0].name}")
            process_file(files[0])
        else:
            # Se ci sono più file, usa il processo batch
            print(f"📦 Processamento batch di {len(files)} file:")
            for f in files:
                print(f"   - {f.name}")
            process_batch(files)

    def stop(self):
        """Ferma il collector e processa eventuali file pendenti."""
        self.active = False
        with self.lock:
            if self.pending_files:
                print(f"⚠️ Processamento degli ultimi {len(self.pending_files)} file prima della chiusura...")
                self._process_batch(self.pending_files.copy())
                self.pending_files.clear()


class FolderWatcher:
    """
    Gestisce l'osservazione di una cartella e il trigger dell'elaborazione file.
    Supporta modalità singola (process_mode='single') o batch (process_mode='batch').
    """
    def __init__(self, folder: str, on_stable_file=None, stable_seconds: float = 3.0,
                 process_mode: str = 'batch', batch_timeout: float = 10.0):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.process_mode = process_mode
        self.batch_collector = BatchCollector(batch_timeout) if process_mode == 'batch' else None
        self.event_handler = StableFileHandler(self.folder, on_stable_file or self._on_file_ready, stable_seconds)
        self.observer = Observer()

    def _on_file_ready(self, path: Path):
        print(f"👀 Nuovo file rilevato: {path.name}")
        if self.process_mode == 'batch':
            self.batch_collector.add_file(path)
        else:
            process_file(path)

    def start(self):
        print(f"🛰️ Watcher attivo su: {self.folder}")
        print(f"📋 Modalità: {self.process_mode.upper()}")

        # 1️⃣ Elabora subito i file già presenti
        existing_files = list(self.folder.glob("*.xml"))
        if existing_files:
            print(f"📁 File pre-esistenti trovati: {len(existing_files)}")
            for file in existing_files:
                if is_supported(file):
                    if self.process_mode == 'batch':
                        self.batch_collector.add_file(file)
                    else:
                        threading.Thread(target=self.event_handler.on_stable_file, args=(file,), daemon=True).start()

        # 2️⃣ Avvia l'osservatore in tempo reale
        self.observer.schedule(self.event_handler, str(self.folder), recursive=False)
        self.observer.start()

    def stop(self):
        print("🛑 Watcher fermato")
        self.event_handler.stop()
        if self.batch_collector:
            self.batch_collector.stop()
        self.observer.stop()
        self.observer.join()


def start_watcher(process_mode: str = 'batch', batch_timeout: float = 10.0):
    """
    Funzione di utilità per avviare il watcher in un thread separato (richiamata da tray_app).

    Args:
        process_mode: 'single' per processare file uno alla volta, 'batch' per processare batch multipli
        batch_timeout: Tempo in secondi di attesa per raccogliere altri file nel batch (default: 10.0)
    """
    watch_folder = Path(__file__).resolve().parents[2] / "watched"
    watcher = FolderWatcher(str(watch_folder), process_mode=process_mode, batch_timeout=batch_timeout)
    watcher.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
