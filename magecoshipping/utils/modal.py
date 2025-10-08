import ctypes
import os
import subprocess
from pathlib import Path

# Windows MessageBox constants
MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001
MB_ICONINFORMATION = 0x00000040
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000
MB_TASKMODAL = 0x00002000
IDOK = 1
IDCANCEL = 2

def show_modal(title: str, message: str, open_path: str | None = None):
    """
    Mostra una finestra modale personalizzata usando Win32 MessageBox:
    - Titolo e messaggio personalizzabili
    - Opzione per aprire cartella dopo
    - Always-on-top, blocca l'interazione fino alla chiusura
    - Thread-safe (può essere chiamata da qualsiasi thread)
    """
    # Prepara il messaggio
    full_message = message
    
    # Se c'è un percorso, aggiungi l'opzione nel messaggio e nei pulsanti
    if open_path and Path(open_path).exists():
        full_message += "\n\nVuoi aprire la cartella?"
        flags = MB_OKCANCEL | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST | MB_TASKMODAL
        
        # Mostra il dialog
        result = ctypes.windll.user32.MessageBoxW(None, full_message, title, flags)
        
        # Se l'utente clicca OK, apri la cartella
        if result == IDOK:
            try:
                # Usa explorer per aprire la cartella
                if os.name == 'nt':
                    os.startfile(open_path)
                else:
                    # Fallback per altri OS (anche se questo codice è Win32-specific)
                    subprocess.Popen(['xdg-open', open_path])
            except Exception as e:
                # Mostra errore se l'apertura fallisce
                error_msg = f"Impossibile aprire la cartella:\n{str(e)}"
                ctypes.windll.user32.MessageBoxW(None, error_msg, "Errore", 
                                                MB_OK | MB_ICONINFORMATION | MB_TOPMOST)
    else:
        # Solo messaggio informativo senza opzione di apertura
        flags = MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST | MB_TASKMODAL
        ctypes.windll.user32.MessageBoxW(None, full_message, title, flags)
