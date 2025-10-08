# src/processor.py
from pathlib import Path
import xml.etree.ElementTree as ET

def is_supported(path: Path) -> bool:
    return path.suffix.lower() == ".xml"

def parse_file(path: Path) -> tuple[bool, str]:
    """
    Ritorna (ok, info_oppure_errore)
    - ok=True  => info con un riassunto (es. root tag)
    - ok=False => stringa con il motivo dell'errore
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        # info sintetica
        return True, f"XML valido. Root: <{root.tag}>"
    except ET.ParseError as e:
        return False, f"XML non valido: {e}"
    except Exception as e:
        return False, f"Errore lettura: {e}"
