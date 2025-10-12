import xml.etree.ElementTree as ET
import re

CATEGORY_MAP = {
    "AUTO": "AUTOVETTURA",
    "AUTOV": "AUTOVETTURA",
    "AV": "AUTOVETTURA",
    "CM": "CASSA MOBILE",
    "BIS": "BISARCA",
    "BIL": "BILICO",
    "ART": "AUTOARTICOLATO",
    "ATR": "AUTOTRENO",
    "CAM": "CAMION",
    "AC": "AUTOCARRO",
    "FUR": "FURGONE",
    "RIM": "RIMORCHIO",
    "SEM": "SEMIRIMORCHIO"
}

MULTI_ROW_TYPES = {"AUTOVETTURA", "CASSA MOBILE", "BISARCA"}
DUAL_TARGA_TYPES = {"AUTOARTICOLATO", "BILICO", "AUTOTRENO"}


# ============================================================
# PARSING XML COMPLETO
# ============================================================

def parse_invoice(xml_path: str) -> dict:
    """
    Restituisce un dizionario completo contenente:
    - dati fornitore
    - dati cliente
    - intestazione documento
    - elenco righe dettagliate (descrizione, quantità, prezzo, analisi)
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    ns = {"p": root.tag.split('}')[0].strip('{')}

    supplier = extract_supplier(root, ns)
    customer = extract_customer(root, ns)
    document = extract_document_info(root, ns)
    lines = [extract_line_data(line) for line in root.findall(".//p:DettaglioLinee", ns)]

    return {
        "supplier": supplier,
        "customer": customer,
        "document": document,
        "lines": lines
    }


# ============================================================
# FUNZIONI DI ESTRAZIONE XML
# ============================================================
def get_first_by_tag(root, tag_name):
    """Restituisce il primo elemento con nome locale (senza namespace)."""
    for elem in root.iter():
        if elem.tag.endswith(tag_name):
            return elem
    return None


def safe_findtext(node, tag_name, default=None):
    """Restituisce il testo di un sotto-nodo (senza namespace) se esiste."""
    if node is None:
        return default
    for child in node.iter():
        if child.tag.endswith(tag_name):
            return child.text.strip() if child.text else default
    return default


def extract_supplier(root, ns=None):
    node = get_first_by_tag(root, "CedentePrestatore")
    if node is None:
        return {}
    return {
        "vat": safe_findtext(node, "IdCodice"),
        "name": safe_findtext(node, "Denominazione"),
        "address": safe_findtext(node, "Indirizzo"),
        "city": safe_findtext(node, "Comune"),
        "province": safe_findtext(node, "Provincia"),
    }


def extract_customer(root, ns=None):
    node = get_first_by_tag(root, "CessionarioCommittente")
    if node is None:
        return {}
    return {
        "name": safe_findtext(node, "Denominazione"),
        "vat": safe_findtext(node, "IdCodice"),
    }


def extract_document(root, ns=None):
    node = get_first_by_tag(root, "DatiGeneraliDocumento")
    if node is None:
        return {}
    return {
        "numero": safe_findtext(node, "Numero"),
        "data": safe_findtext(node, "Data"),
        "totale": float(safe_findtext(node, "ImportoTotaleDocumento", "0") or 0),
        "divisa": safe_findtext(node, "Divisa"),
    }


def extract_document_info(root, ns):
    node = root.find(".//p:DatiGeneraliDocumento", ns)
    return {
        "numero": node.findtext("p:Numero", namespaces=ns),
        "data": node.findtext("p:Data", namespaces=ns),
        "totale": float(node.findtext("p:ImportoTotaleDocumento", namespaces=ns)),
        "divisa": node.findtext("p:Divisa", namespaces=ns)
    }


def extract_line_data(line):
    desc = line.findtext("Descrizione")
    qty = float(line.findtext("Quantita"))
    prezzo = float(line.findtext("PrezzoTotale"))
    parsed = parse_description(desc)
    return {
        "descrizione": desc,
        "quantita": qty,
        "prezzo": prezzo,
        **parsed
    }


# ============================================================
# PARSING DELLA DESCRIZIONE (TESTO LIBERO)
# ============================================================

def parse_description(text: str) -> dict:
    """
    Interpreta la descrizione di un rigo fattura.
    """
    text = text.upper()
    result = {"veicolo_tipo": None, "tratta": None, "targhe": []}

    for abbr, full in CATEGORY_MAP.items():
        if abbr in text:
            result["veicolo_tipo"] = full
            break

    tratta = re.search(r"[A-Z]{2}/[A-Z]{2}", text)
    if tratta:
        result["tratta"] = tratta.group(0)

    targhe = re.findall(r"[A-Z]{1,2}\\d{3,4}[A-Z]{1,2}", text)
    result["targhe"] = targhe

    return result
