
import re
import pandas as pd
from dateutil import parser as date_parser


# ─────────────────────────────────────────────
# GENERAL UTILITIES
# ─────────────────────────────────────────────

def safe_float(value) -> float:
    """Convert any value to float safely, return 0.0 on failure."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").replace(" ", "").strip()
        return float(cleaned)
    except:
        return 0.0


def safe_str(value, default="Unknown") -> str:
    """Convert value to stripped string, return default if null."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    return str(value).strip()


def safe_date(value) -> str:
    """Parse any date format to YYYY-MM-DD string. Return None if unparseable."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return date_parser.parse(str(value)).strftime("%Y-%m-%d")
    except:
        return None


# ─────────────────────────────────────────────
# SECTOR NORMALIZATION
# ─────────────────────────────────────────────

SECTOR_MAP = {
    "renewables": "Renewables",
    "renewable": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "mining": "Mining",
    "mine": "Mining",
    "railways": "Railways",
    "railway": "Railways",
    "rail": "Railways",
    "powerline": "Powerline",
    "power line": "Powerline",
    "power": "Powerline",
    "construction": "Construction",
    "dsp": "DSP",
    "tender": "Tender",
    "manufacturing": "Manufacturing",
    "aviation": "Aviation",
    "security": "Security and Surveillance",
    "surveillance": "Security and Surveillance",
    "others": "Others",
    "other": "Others",
}

def normalize_sector(value: str) -> str:
    """Normalize sector names to canonical form."""
    raw = safe_str(value, "Unknown").lower().strip()
    if raw == "unknown":
        return "Unknown"
    for key, canonical in SECTOR_MAP.items():
        if key in raw:
            return canonical
    return safe_str(value, "Unknown").title()


# ─────────────────────────────────────────────
# DEAL STATUS NORMALIZATION
# ─────────────────────────────────────────────

def normalize_deal_status(value: str) -> str:
    """Normalize Deal Status: Won / Dead / Open / On Hold / Unknown."""
    raw = safe_str(value, "Unknown").lower().strip()
    if raw in ["won", "win"]:
        return "Won"
    if raw in ["dead", "lost", "closed lost"]:
        return "Dead"
    if raw in ["open", "active"]:
        return "Open"
    if raw in ["on hold", "hold", "paused"]:
        return "On Hold"
    return safe_str(value, "Unknown").title()


# ─────────────────────────────────────────────
# DEAL STAGE NORMALIZATION
# ─────────────────────────────────────────────

STAGE_ORDER = {
    "a": 1, "b": 2, "c": 3, "d": 4, "e": 5,
    "f": 6, "g": 7, "h": 8, "i": 9, "j": 10,
    "k": 11, "l": 12, "m": 13, "n": 14, "o": 15,
}

def normalize_deal_stage(value: str) -> str:
    """Return canonical deal stage string. Header rows return None."""
    raw = safe_str(value, "").strip()
    if raw.lower() in ["deal stage", "", "unknown"]:
        return None  # header row or empty — filter out
    return raw

def get_stage_order(stage: str) -> int:
    """Return numeric order of a deal stage for sorting."""
    if not stage:
        return 99
    first_char = stage.strip()[0].lower()
    return STAGE_ORDER.get(first_char, 99)


# ─────────────────────────────────────────────
# CLOSURE PROBABILITY NORMALIZATION
# ─────────────────────────────────────────────

def normalize_probability(value: str) -> str:
    """Normalize closure probability to High / Medium / Low / Unknown."""
    raw = safe_str(value, "Unknown").lower().strip()
    if raw in ["high", "h"]:
        return "High"
    if raw in ["medium", "med", "m"]:
        return "Medium"
    if raw in ["low", "l"]:
        return "Low"
    return "Unknown"


# ─────────────────────────────────────────────
# EXECUTION STATUS NORMALIZATION (Work Orders)
# ─────────────────────────────────────────────

def normalize_execution_status(value: str) -> str:
    """Normalize WO execution status to clean canonical values."""
    raw = safe_str(value, "Unknown").lower().strip()
    if "complet" in raw:
        return "Completed"
    if "ongoing" in raw or "current month" in raw:
        return "Ongoing"
    if "not started" in raw:
        return "Not Started"
    if "pause" in raw or "struck" in raw:
        return "Paused"
    if "partial" in raw:
        return "Partially Completed"
    if "pending" in raw or "client" in raw:
        return "Details Pending"
    return safe_str(value, "Unknown").title()


# ─────────────────────────────────────────────
# INVOICE STATUS NORMALIZATION (Work Orders)
# ─────────────────────────────────────────────

def normalize_invoice_status(value: str) -> str:
    """Normalize invoice status — handle freeform entries like 'Billed- Visit 7'."""
    raw = safe_str(value, "Unknown").lower().strip()
    if raw in ["unknown", ""]:
        return "Unknown"
    if "fully" in raw or raw == "billed":
        return "Fully Billed"
    if "partial" in raw or "visit" in raw:
        return "Partially Billed"
    if "not" in raw:
        return "Not Billed Yet"
    if "stuck" in raw:
        return "Stuck"
    return safe_str(value, "Unknown").title()


# ─────────────────────────────────────────────
# BILLING STATUS NORMALIZATION (Work Orders)
# ─────────────────────────────────────────────

def normalize_billing_status(value: str) -> str:
    """Fix typos like 'BIlled' → 'Billed'."""
    raw = safe_str(value, "Unknown").strip()
    if raw.lower() == "billed" or raw == "BIlled":
        return "Billed"
    if raw.lower() == "update required":
        return "Update Required"
    if raw.lower() == "not billable":
        return "Not Billable"
    if raw.lower() in ["partially billed", "partial"]:
        return "Partially Billed"
    if raw.lower() == "stuck":
        return "Stuck"
    return raw


# ─────────────────────────────────────────────
# SKYLARK SOFTWARE NORMALIZATION
# ─────────────────────────────────────────────

def normalize_software_flag(value: str) -> str:
    """Normalize Skylark software platform column."""
    raw = safe_str(value, "NONE").upper().strip()
    if raw in ["NONE", "NO", "N", "0", "FALSE", "UNKNOWN", ""]:
        return "NONE"
    if raw in ["SPECTRA + DMO", "DMO + SPECTRA"]:
        return "SPECTRA + DMO"
    if raw == "SPECTRA":
        return "SPECTRA"
    if raw == "DMO":
        return "DMO"
    return raw


# ─────────────────────────────────────────────
# QUANTITY PARSER (Work Orders)
# ─────────────────────────────────────────────

def parse_quantity(value) -> dict:
    """
    Parse messy quantity strings like:
    '5360 HA', '115HA', '45days', '304 RKM', 'Rate based on MW slabs', '1'
    Returns: {"quantity": float|None, "unit": str|None, "raw": str, "parseable": bool}
    """
    raw = safe_str(value, "")
    if not raw or raw == "Unknown":
        return {"quantity": None, "unit": None, "raw": None, "parseable": False}

    # Try to extract leading number + unit
    match = re.match(r"^([\d,\.]+)\s*([a-zA-Z\.]*)", raw.strip())
    if match:
        try:
            qty = float(match.group(1).replace(",", ""))
            unit = match.group(2).strip().upper() if match.group(2) else "UNIT"
            return {"quantity": qty, "unit": unit, "raw": raw, "parseable": True}
        except:
            pass

    # Unparseable freeform text
    return {"quantity": None, "unit": None, "raw": raw, "parseable": False}


# ─────────────────────────────────────────────
# INVOICE NUMBER PARSER
# ─────────────────────────────────────────────

def parse_invoice_number(value) -> dict:
    """
    Parse invoice numbers like 'SDPL/FY25-26/916'
    Returns: {"raw": str, "prefix": str, "fy": str, "sequence": int|None}
    """
    raw = safe_str(value, "")
    if not raw or raw == "Unknown":
        return {"raw": None, "prefix": None, "fy": None, "sequence": None}

    parts = raw.strip().split("/")
    return {
        "raw": raw,
        "prefix": parts[0] if len(parts) > 0 else None,
        "fy": parts[1] if len(parts) > 1 else None,
        "sequence": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None
    }


# ─────────────────────────────────────────────
# FULL ROW CLEANERS
# ─────────────────────────────────────────────

def clean_deal_row(raw: dict) -> dict:
    """Clean and normalize a single Deals board row."""
    return {
        "deal_name": safe_str(raw.get("deal_name"), "Unnamed Deal"),
        "owner_code": safe_str(raw.get("owner_code"), "Unknown"),
        "client_code": safe_str(raw.get("client_code"), "Unknown"),
        "deal_status": normalize_deal_status(raw.get("deal_status")),
        "close_date": safe_date(raw.get("close_date")),
        "tentative_close_date": safe_date(raw.get("tentative_close_date")),
        "closure_probability": normalize_probability(raw.get("closure_probability")),
        "deal_value": safe_float(raw.get("deal_value")),
        "deal_stage": normalize_deal_stage(raw.get("deal_stage")),
        "stage_order": get_stage_order(safe_str(raw.get("deal_stage"), "")),
        "product_deal": safe_str(raw.get("product_deal"), "Unknown"),
        "sector": normalize_sector(raw.get("sector")),
        "created_date": safe_date(raw.get("created_date")),
    }


def clean_work_order_row(raw: dict) -> dict:
    """Clean and normalize a single Work Orders board row."""
    qty = parse_quantity(raw.get("quantity_per_po"))
    inv = parse_invoice_number(raw.get("invoice_number"))

    return {
        "deal_name": safe_str(raw.get("deal_name"), "Unnamed"),
        "customer_code": safe_str(raw.get("customer_code"), "Unknown"),
        "serial_number": safe_str(raw.get("serial_number"), "Unknown"),
        "nature_of_work": safe_str(raw.get("nature_of_work"), "Unknown"),
        "execution_status": normalize_execution_status(raw.get("execution_status")),
        "sector": normalize_sector(raw.get("sector")),
        "type_of_work": safe_str(raw.get("type_of_work"), "Unknown"),
        "document_type": safe_str(raw.get("document_type"), "Unknown"),
        "software_platform": normalize_software_flag(raw.get("software_platform")),
        "bd_kam_code": safe_str(raw.get("bd_kam_code"), "Unknown"),
        "date_of_po": safe_date(raw.get("date_of_po")),
        "probable_start_date": safe_date(raw.get("probable_start_date")),
        "probable_end_date": safe_date(raw.get("probable_end_date")),
        "data_delivery_date": safe_date(raw.get("data_delivery_date")),
        "last_invoice_date": safe_date(raw.get("last_invoice_date")),
        "invoice_number": inv,
        "amount_excl_gst": safe_float(raw.get("amount_excl_gst")),
        "amount_incl_gst": safe_float(raw.get("amount_incl_gst")),
        "billed_excl_gst": safe_float(raw.get("billed_excl_gst")),
        "billed_incl_gst": safe_float(raw.get("billed_incl_gst")),
        "collected_incl_gst": safe_float(raw.get("collected_incl_gst")),
        "to_bill_excl_gst": safe_float(raw.get("to_bill_excl_gst")),
        "to_bill_incl_gst": safe_float(raw.get("to_bill_incl_gst")),
        "amount_receivable": safe_float(raw.get("amount_receivable")),
        "ar_priority": safe_str(raw.get("ar_priority"), "No"),
        "quantity_raw": qty["raw"],
        "quantity_value": qty["quantity"],
        "quantity_unit": qty["unit"],
        "quantity_parseable": qty["parseable"],
        "quantity_billed": safe_float(raw.get("quantity_billed")),
        "balance_quantity": safe_float(raw.get("balance_quantity")),
        "invoice_status": normalize_invoice_status(raw.get("invoice_status")),
        "wo_status": safe_str(raw.get("wo_status"), "Unknown"),
        "billing_status": normalize_billing_status(raw.get("billing_status")),
        "actual_billing_month": safe_date(raw.get("actual_billing_month")),
    }


# ─────────────────────────────────────────────
# DATA QUALITY REPORT
# ─────────────────────────────────────────────

def get_data_quality_caveats(cleaned_rows: list, board: str) -> str:
    """
    Generate a human-readable data quality caveat string
    to append to agent responses when data is incomplete.
    """
    total = len(cleaned_rows)
    if total == 0:
        return "⚠️ No data returned from Monday.com."

    caveats = []

    if board == "deals":
        missing_value = sum(1 for r in cleaned_rows if r.get("deal_value", 0) == 0)
        missing_close = sum(1 for r in cleaned_rows if not r.get("close_date"))
        if missing_value > 0:
            caveats.append(
                f"deal value is missing for {missing_value}/{total} deals "
                f"— actual figures may be higher"
            )
        if missing_close > 0:
            caveats.append(
                f"actual close date is missing for {missing_close}/{total} deals "
                f"— tentative close date used where available"
            )

    elif board == "work_orders":
        missing_collected = sum(1 for r in cleaned_rows if r.get("collected_incl_gst", 0) == 0)
        unparseable_qty = sum(1 for r in cleaned_rows if not r.get("quantity_parseable") and r.get("quantity_raw"))
        if missing_collected > 0:
            caveats.append(
                f"collected amount is missing for {missing_collected}/{total} work orders"
            )
        if unparseable_qty > 0:
            caveats.append(
                f"{unparseable_qty} work orders have non-numeric quantity values "
                f"(e.g., 'Rate based on MW slabs') — excluded from quantity totals"
            )

    if not caveats:
        return ""
    return "⚠️ Data quality note: " + "; ".join(caveats) + "."
