from pathlib import Path
import xml.etree.ElementTree as ET
from magecoshipping.webui.server import start_review_server

def is_supported(path: Path) -> bool:
    """
    Verifica se il file ha estensione XML.
    """
    return path.suffix.lower() == ".xml"


def parse_file(path: Path) -> tuple[bool, dict | str]:
    """
    Analizza il file XML FatturaPA e restituisce:
      - (True, dict)  se parsing ok
      - (False, errore) se non valido
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Namespace FatturaPA (di solito inizia con {http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2})
        ns = {"p": root.tag[root.tag.find("{")+1 : root.tag.find("}")]} if "}" in root.tag else {}

        # Estrazione dati base (dipende dalla struttura FatturaPA)
        cliente = root.findtext(".//p:CessionarioCommittente/p:DatiAnagrafici/p:Anagrafica/p:Denominazione", namespaces=ns)
        piva_cliente = root.findtext(".//p:CessionarioCommittente/p:DatiAnagrafici/p:IdFiscaleIVA/p:IdCodice", namespaces=ns)
        tratta = root.findtext(".//p:DatiBeniServizi/p:DettaglioLinee/p:Descrizione", namespaces=ns)
        costo = root.findtext(".//p:DatiBeniServizi/p:DatiRiepilogo/p:ImponibileImporto", namespaces=ns)

        # fallback se alcuni dati mancano
        data_dict = {
            "file_name": path.name,
            "cliente": cliente or "N/D",
            "piva_cliente": piva_cliente or "N/D",
            "tratta": tratta or "N/D",
            "costo": float(costo) if costo else 0.0,
            "original_path": str(path),
            "status": "pending"
        }

        return True, data_dict

    except ET.ParseError as e:
        return False, f"XML non valido: {e}"
    except Exception as e:
        return False, f"Errore lettura/parsing: {e}"


def process_file(path: Path):
    """
    Funzione chiamata dal watcher.
    - Esegue parsing
    - Mostra la finestra di revisione (WebUI)
    """
    print(f"📄 Elaborazione file: {path}")

    ok, result = parse_file(path)

    if not ok:
        print(f"❌ Parsing fallito: {result}")
        return False

    data_dict = result
    print(f"✅ XML valido, apertura WebUI per revisione...")
    start_review_server(data_dict)
