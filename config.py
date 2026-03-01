
import os
from dotenv import load_dotenv

load_dotenv()

# ── Monday.com ───────────────────────────────
MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"
MONDAY_API_VERSION = "2024-01"

DEALS_BOARD_ID = os.getenv("DEALS_BOARD_ID")
WORK_ORDERS_BOARD_ID = os.getenv("WORK_ORDERS_BOARD_ID")

# ── Groq LLM ───────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Deals Board Column IDs ────────────────────
DEALS_COLUMNS = {
    "deal_name":           "name",
    "owner_code":          "text_mm11v1b",
    "client_code":         "text_mm11jzj3",
    "deal_status":         "color_mm112fcd",
    "close_date":          "date_mm11ndbx",
    "closure_probability": "dropdown_mm117aya",
    "deal_value":          "numeric_mm11r58j",
    "tentative_close_date":"date_mm11e8wm",
    "deal_stage":          "dropdown_mm116q5h",
    "product_deal":        "dropdown_mm11fnfh",
    "sector":              "dropdown_mm11fgde",
    "created_date":        "date_mm11p1jh",
}

# ── Work Orders Board Column IDs ──────────────
WO_COLUMNS = {
    "deal_name":           "name",
    "customer_code":       "text_mm113k44",
    "serial_number":       "text_mm11n8f0",
    "nature_of_work":      "dropdown_mm11btvr",
    "last_exec_month":     "text_mm118mmc",
    "execution_status":    "color_mm11pjmg",
    "data_delivery_date":  "date_mm11p5n0",
    "date_of_po":          "date_mm113bdf",
    "document_type":       "dropdown_mm11p3ga",
    "probable_start_date": "date_mm11v4gp",
    "probable_end_date":   "date_mm119rwk",
    "bd_kam_code":         "text_mm115t5v",
    "sector":              "dropdown_mm1181eg",
    "type_of_work":        "text_mm11vzcg",
    "software_platform":   "dropdown_mm11kkt7",
    "last_invoice_date":   "date_mm11ywgy",
    "invoice_number":      "text_mm11nnt3",
    "amount_excl_gst":     "numeric_mm115v4n",
    "amount_incl_gst":     "numeric_mm11xbsz",
    "billed_excl_gst":     "numeric_mm116fd3",
    "billed_incl_gst":     "numeric_mm11wbm4",
    "collected_incl_gst":  "numeric_mm11e43x",
    "to_bill_excl_gst":    "numeric_mm117g53",
    "to_bill_incl_gst":    "numeric_mm11w4ty",
    "amount_receivable":   "numeric_mm11a6gh",
    "ar_priority":         "dropdown_mm118xwh",
    "quantity_by_ops":     "text_mm11ajze",
    "quantity_per_po":     "text_mm11187n",
    "quantity_billed":     "numeric_mm11jp6s",
    "balance_quantity":    "numeric_mm114mhq",
    "invoice_status":      "color_mm11fpba",
    "wo_status":           "color_mm11ne9z",
    "actual_billing_month":"text_mm115cn1",
    "billing_status":      "color_mm11dfhk",
}

# ── Validation ────────────────────────────────
def validate_env():
    """Call this at startup to catch missing env variables early."""
    missing = []
    for var in ["MONDAY_API_KEY", "DEALS_BOARD_ID", "WORK_ORDERS_BOARD_ID", "GROQ_API_KEY"]:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Please check your .env file."
        )
