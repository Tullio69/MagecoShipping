import xml.etree.ElementTree as ET
import re
# --- LOG DIAGNOSTICO (puoi rimuoverlo dopo i test) ---
import logging
logger = logging.getLogger(__name__)
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

# --- sostituisci TUTTA la sezione "PARSING DELLA DESCRIZIONE" ---

IGNORE_WORDS = {"TIRRENIA", "GRIMALDI", "GNV"}
PLATE_REGEX = r"\b[A-Z]{2}\d{3}[A-Z]{2}\b"      # AA123BB
TRATTA_REGEX = r"\b[A-Z]{1,3}/[A-Z]{1,3}\b"     # NA/PA

VEHICLE_PRIORITY = [
    "CASSA MOBILE",
    "AUTOARTICOLATO", "BILICO", "AUTOTRENO", "SEMIRIMORCHIO", "RIMORCHIO",
    "AUTOCARRO", "FURGONE", "CAMION",
    "MOTOVEICOLO",
    "AUTOVETTURE"
]

VEHICLE_SYNONYMS = {
    "CASSA MOBILE": ["CASSA MOBILE", "CASSA", "UDC", "U.D.C."],
    "AUTOARTICOLATO": ["AUTOARTICOLATO", "AUTOART.", "ART", "TIR"],
    "BILICO": ["BILICO", "BIL"],
    "AUTOTRENO": ["AUTOTRENO", "ATR"],
    "SEMIRIMORCHIO": ["SEMIRIMORCHIO", "SEM"],
    "RIMORCHIO": ["RIMORCHIO", "RIM"],
    "AUTOCARRO": ["AUTOCARRO", "AC", "CAMION", "CAM"],
    "FURGONE": ["FURGONE", "FURGONATO", "FUR"],
    "MOTOVEICOLO": ["MOTO", "MOTOCICLO", "SCOOTER"],
    "AUTOVETTURE": ["AUTO", "AUTOVETTURA", "AUTOV"]
}

def _normalize_text(s: str) -> str:
    s = (s or "").upper()
    s = re.sub(r"[\/\|\-,\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _match_vehicle_type(text: str) -> str | None:
    t = _normalize_text(text)
    for w in IGNORE_WORDS:
        t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
    for category in VEHICLE_PRIORITY:
        for syn in VEHICLE_SYNONYMS.get(category, []):
            if re.search(rf"\b{re.escape(syn)}\b", t):
                # appiattimenti verso categorie canoniche
                if category in {"BILICO", "AUTOTRENO", "SEMIRIMORCHIO", "RIMORCHIO"}:
                    return "AUTOARTICOLATO"
                if category == "FURGONE":
                    return "AUTOCARRO"
                return category
    return None

# ============================================================
# PARSING DELLA DESCRIZIONE (TESTO LIBERO)
# ============================================================

IGNORE_WORDS = {"TIRRENIA", "GRIMALDI", "GNV"}   # non devono attivare match (es. TIR in TIRRENIA)
PLATE_REGEX  = r"\b[A-Z]{2}\d{3}[A-Z]{2}\b"      # AA123BB
TRATTA_REGEX = r"\b[A-Z]{1,3}/[A-Z]{1,3}\b"      # NA/PA

# Priorità: specifici prima, generici dopo
VEHICLE_PRIORITY = [
    "CASSA MOBILE",
    "AUTOARTICOLATO", "BILICO", "AUTOTRENO", "SEMIRIMORCHIO", "RIMORCHIO",
    "AUTOCARRO", "FURGONE", "CAMION",
    "MOTOVEICOLO",
    "AUTOVETTURE",  # generica, per ultima
]

VEHICLE_SYNONYMS = {
    "CASSA MOBILE":    ["CASSA MOBILE", "CASSA", "UDC", "U.D.C."],
    "AUTOARTICOLATO":  ["AUTOARTICOLATO", "AUTOART.", "ART", "TIR"],
    "BILICO":          ["BILICO", "BIL"],
    "AUTOTRENO":       ["AUTOTRENO", "ATR"],
    "SEMIRIMORCHIO":   ["SEMIRIMORCHIO", "SEM"],
    "RIMORCHIO":       ["RIMORCHIO", "RIM"],
    "AUTOCARRO":       ["AUTOCARRO", "AC", "CAMION", "CAM"],
    "FURGONE":         ["FURGONE", "FURGONATO", "FUR"],
    "MOTOVEICOLO":     ["MOTO", "MOTOCICLO", "SCOOTER"],
    "AUTOVETTURE":     ["AUTO", "AUTOVETTURA", "AUTOV"],
}

def _normalize_text(s: str) -> str:
    s = (s or "").upper()
    s = re.sub(r"[\/\|\-,\s]+", " ", s)     # normalizza separatori DOPO aver estratto NA/PA e targhe
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _match_vehicle_type(text: str) -> str | None:
    t = _normalize_text(text)
    # rimuovi parole da ignorare (evita "TIR" dentro "TIRRENIA")
    for w in IGNORE_WORDS:
        t = re.sub(rf"\b{re.escape(w)}\b", " ", t)
    # scan per priorità e parole intere
    for category in VEHICLE_PRIORITY:
        for syn in VEHICLE_SYNONYMS.get(category, []):
            if re.search(rf"\b{re.escape(syn)}\b", t):
                # appiattimenti verso categorie canoniche
                if category in {"BILICO", "AUTOTRENO", "SEMIRIMORCHIO", "RIMORCHIO"}:
                    return "AUTOARTICOLATO"
                if category == "FURGONE":
                    return "AUTOCARRO"
                return category
    return None

def parse_description(text: str) -> dict:
    """
    1) Estrae TRATTA e TARGHE dal testo grezzo (mantiene lo slash).
    2) Riconosce TIPO VEICOLO su testo normalizzato con priorità e confini di parola.
    """
    raw = (text or "").upper()

    # 1) TRATTA e TARGHE prima della normalizzazione
    m_tratta = re.search(TRATTA_REGEX, raw)
    tratta = m_tratta.group(0) if m_tratta else None
    targhe = re.findall(PLATE_REGEX, raw)

    # 2) Tipo veicolo (parole intere + priorità)
    tipo_veicolo = _match_vehicle_type(raw) or "N/D"
    logger.info("parse_description -> tipo=%s tratta=%s targhe=%s", tipo_veicolo, tratta, ";".join(targhe))
    print("[parse_description]", {"tipo": tipo_veicolo, "tratta": tratta, "targhe": targhe})
    return {
        "tipo_veicolo": tipo_veicolo,   # <-- allineato al DB
        "tratta": tratta,
        "targhe": targhe,
    }

