from pathlib import Path
import xml.etree.ElementTree as ET
import re
import threading
from magecoshipping.webui.server import start_review_server

# Lock per serializzare l'elaborazione dei file
_processing_lock = threading.Lock()


def is_supported(path: Path) -> bool:
    """Verifica se il file ha estensione XML supportata."""
    return path.suffix.lower() == ".xml"


def parse_file(path: Path) -> tuple[bool, dict | str]:
    """
    Analizza una FatturaPA:
    - Estrae tutte le righe così come presenti nel documento.
    - Applica regole di riconoscimento convenzioni MagecoShipping.
    - Ogni riga contiene flag recognized/include.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Namespace dinamico (per fatturePA standard)
        ns = {}
        if "}" in root.tag:
            ns["f"] = root.tag[root.tag.find("{") + 1 : root.tag.find("}")]

        # --- 1️⃣ Dati Cliente e Fornitore ---
        cliente = root.findtext(".//f:CessionarioCommittente/f:DatiAnagrafici/f:Anagrafica/f:Denominazione", namespaces=ns)
        piva_cliente = root.findtext(".//f:CessionarioCommittente/f:DatiAnagrafici/f:IdFiscaleIVA/f:IdCodice", namespaces=ns)
        if not cliente or not piva_cliente:
            cliente = root.findtext(".//CessionarioCommittente/DatiAnagrafici/Anagrafica/Denominazione") or cliente
            piva_cliente = root.findtext(".//CessionarioCommittente/DatiAnagrafici/IdFiscaleIVA/IdCodice") or piva_cliente

        # Fornitore
        fornitore = root.findtext(".//f:CedentePrestatore/f:DatiAnagrafici/f:Anagrafica/f:Denominazione", namespaces=ns)
        piva_fornitore = root.findtext(".//f:CedentePrestatore/f:DatiAnagrafici/f:IdFiscaleIVA/f:IdCodice", namespaces=ns)
        if not fornitore:
            fornitore = root.findtext(".//CedentePrestatore/DatiAnagrafici/Anagrafica/Denominazione")
        if not piva_fornitore:
            piva_fornitore = root.findtext(".//CedentePrestatore/DatiAnagrafici/IdFiscaleIVA/IdCodice")

        data_doc = (
            root.findtext(".//f:DatiGeneraliDocumento/f:Data", namespaces=ns)
            or root.findtext(".//DatiGeneraliDocumento/Data")
        )
        num_doc = (
            root.findtext(".//f:DatiGeneraliDocumento/f:Numero", namespaces=ns)
            or root.findtext(".//DatiGeneraliDocumento/Numero")
        )
        totale_doc = (
            root.findtext(".//f:DatiGeneraliDocumento/f:ImportoTotaleDocumento", namespaces=ns)
            or root.findtext(".//DatiGeneraliDocumento/ImportoTotaleDocumento")
        )

        # --- 2️⃣ Righe ---
        dettagli = root.findall(".//f:DatiBeniServizi/f:DettaglioLinee", namespaces=ns)
        if not dettagli:
            dettagli = root.findall(".//DatiBeniServizi/DettaglioLinee")

        lines = []
        for dett in dettagli:
            descr = (dett.findtext("f:Descrizione", namespaces=ns) or
                     dett.findtext("Descrizione") or "").strip()
            imponibile = (dett.findtext("f:PrezzoTotale", namespaces=ns) or
                          dett.findtext("PrezzoTotale") or "0")

            # --- Regole di riconoscimento convenzioni ---
            tratta = re.search(r"\b[A-Z]{1,3}/[A-Z]{1,3}\b", descr.upper())
            targa = re.search(r"\b[A-Z]{2}\d{3,4}[A-Z]{2}\b", descr.upper())

            tipo_veicolo = "N/D"
            for key, tipo in {
                "autovettur": "AUTOVETTURA",
                "autocarro": "AUTOCARRO",
                "furgon": "FURGONE",
                "bus": "BUS",
                "pullman": "BUS",
                "moto": "MOTO",
            }.items():
                if key in descr.lower():
                    tipo_veicolo = tipo
                    break

            recognized = bool(tratta or targa or tipo_veicolo != "N/D")

            # --- Lettura quantità fattura ---
            quantita_fattura = (dett.findtext("f:Quantita", namespaces=ns) or
                                dett.findtext("Quantita") or "1")

            # --- Ricerca targhe e tratta ---
            targhe = re.findall(r"\b[A-Z]{2}\d{3,4}[A-Z]{2}\b", descr.upper())
            tratta = re.search(r"\b[A-Z]{1,3}/[A-Z]{1,3}\b", descr.upper())

            # --- Quantità reale (numero di targhe individuate) ---
            quantita_reale = len(targhe) if targhe else 1

            # --- Identificazione tipo veicolo ---
            tipo_veicolo = "N/D"
            for key, tipo in {
                "autovettur": "AUTOVETTURA",
                "autocarro": "AUTOCARRO",
                "furgon": "FURGONE",
                "bus": "BUS",
                "pullman": "BUS",
                "moto": "MOTO",
            }.items():
                if key in descr.lower():
                    tipo_veicolo = tipo
                    break

            recognized = bool(tratta or targhe or tipo_veicolo != "N/D")

            lines.append({
                "descrizione_rigo": descr,
                "tratta": tratta.group(0) if tratta else "N/D",
                "targhe": ", ".join(targhe) if targhe else "N/D",
                "tipo_veicolo": tipo_veicolo,
                "quantita_fattura": float(quantita_fattura or 1.0),
                "quantita_reale": float(quantita_reale),
                "costo": float(imponibile or 0.0),
                "recognized": recognized,
                "include": True
            })

        # --- 3️⃣ Dizionario complessivo ---
        data_dict = {
            "file_name": path.name,
            "cliente": cliente or "N/D",
            "piva_cliente": piva_cliente or "N/D",
            "fornitore": fornitore or "N/D",
            "piva_fornitore": piva_fornitore or "N/D",
            "data_doc": data_doc or "",
            "num_doc": num_doc or "",
            "totale_doc": float(totale_doc or 0.0),
            "lines": lines,
            "status": "pending",
            "original_path": str(path)
        }

        print(f"📊 Documento '{path.name}' → {len(lines)} righe lette.")
        riconosciute = len([l for l in lines if l['recognized']])
        print(f"   ✅ {riconosciute} righe riconosciute | ⚠️ {len(lines) - riconosciute} non riconosciute")

        return True, data_dict

    except ET.ParseError as e:
        return False, f"XML non valido: {e}"
    except Exception as e:
        return False, f"Errore parsing: {e}"


def process_file(path: Path):
    """
    Esegue il parsing completo e apre la WebUI per revisione / conferma.
    Usa un lock per serializzare l'elaborazione ed evitare che più file
    vengano processati contemporaneamente.
    """
    with _processing_lock:
        print(f"📄 Elaborazione file: {path}")
        ok, result = parse_file(path)
        if not ok:
            print(f"❌ Errore nel parsing: {result}")
            return

        data_dict = result
        print(f"✅ Parsing completato: {data_dict['file_name']} ({len(data_dict['lines'])} righe)")
        start_review_server(data_dict)

        # Piccola pausa per assicurarsi che il browser si apra prima di processare il prossimo file
        import time
        time.sleep(1)
