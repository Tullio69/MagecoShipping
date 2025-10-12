from pathlib import Path
import xml.etree.ElementTree as ET
from magecoshipping.webui.server import start_review_server

def is_supported(path: Path) -> bool:
    """Verifica se il file ha estensione XML."""
    return path.suffix.lower() == ".xml"


def parse_file(path: Path) -> tuple[bool, dict | str]:
    """
    Analizza un file FatturaPA e restituisce:
      - (True, dict)  se parsing ok
      - (False, errore) se parsing fallito
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Identifica namespace (FatturaPA usa nomi con {namespace}Elemento)
        ns = {}
        if "}" in root.tag:
            ns["f"] = root.tag[root.tag.find("{") + 1 : root.tag.find("}")]

        # 1️⃣ Dati Cliente (CessionarioCommittente)
        cliente = root.findtext(".//f:CessionarioCommittente/f:DatiAnagrafici/f:Anagrafica/f:Denominazione", namespaces=ns)
        piva_cliente = root.findtext(".//f:CessionarioCommittente/f:DatiAnagrafici/f:IdFiscaleIVA/f:IdCodice", namespaces=ns)

        # 2️⃣ Dati del documento
        data_doc = root.findtext(".//f:DatiGeneraliDocumento/f:Data", namespaces=ns)
        num_doc = root.findtext(".//f:DatiGeneraliDocumento/f:Numero", namespaces=ns)
        totale = root.findtext(".//f:DatiGeneraliDocumento/f:ImportoTotaleDocumento", namespaces=ns)

        # 3️⃣ Dati di riga (descrizione / tratta / imponibile)
        prima_linea = root.find(".//f:DatiBeniServizi/f:DettaglioLinee", namespaces=ns)
        tratta = None
        imponibile = None
        if prima_linea is not None:
            tratta = prima_linea.findtext("f:Descrizione", namespaces=ns)
            imponibile = prima_linea.findtext("f:PrezzoTotale", namespaces=ns)

        # fallback in caso di dati mancanti
        data_dict = {
            "file_name": path.name,
            "cliente": cliente or "N/D",
            "piva_cliente": piva_cliente or "N/D",
            "tratta": tratta or "N/D",
            "costo": float(imponibile or totale or 0),
            "data_doc": data_doc or "",
            "num_doc": num_doc or "",
            "original_path": str(path),
            "status": "pending",
        }

        # Verifica minima
        if not cliente or not piva_cliente:
            return False, "Fattura priva di dati cliente / P.IVA"

        return True, data_dict

    except ET.ParseError as e:
        return False, f"XML non valido: {e}"
    except Exception as e:
        return False, f"Errore lettura/parsing: {e}"


def process_file(path: Path):
    """
    Esegue parsing e apre la WebUI per revisione dati.
    """
    print(f"📄 Elaborazione file: {path}")

    ok, result = parse_file(path)
    if not ok:
        print(f"❌ Errore nel parsing: {result}")
        return

    data_dict = result
    print(f"✅ XML valido. Apertura WebUI per revisione dati...")
    start_review_server(data_dict)
