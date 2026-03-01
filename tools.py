
from langchain.tools import tool
from monday_client import fetch_deals, fetch_work_orders
from data_cleaner import (
    clean_deal_row,
    clean_work_order_row,
    get_data_quality_caveats
)
import json
from datetime import datetime
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ─────────────────────────────────────────────
# HELPER — FORMAT CURRENCY
# ─────────────────────────────────────────────

def fmt_inr(amount: float) -> str:
    """Format a float into Indian currency string (Cr / L / raw)."""
    if amount >= 1_00_00_000:
        return f"₹{amount / 1_00_00_000:.2f} Cr"
    elif amount >= 1_00_000:
        return f"₹{amount / 1_00_000:.2f} L"
    else:
        return f"₹{amount:,.0f}"


# ─────────────────────────────────────────────
# QUERY-SPECIFIC FILTERING HELPERS
# ─────────────────────────────────────────────

def _filter_relevant_deals(deals: list, query: str, max_count: int = 10) -> list:
    """Filter deals based on query context to reduce token usage."""
    query_lower = query.lower()
    
    # Status-specific filtering
    if 'open' in query_lower:
        filtered = [d for d in deals if d["deal_status"] == "Open"]
    elif 'won' in query_lower or 'closed' in query_lower:
        filtered = [d for d in deals if d["deal_status"] == "Won"]
    elif 'dead' in query_lower or 'lost' in query_lower:
        filtered = [d for d in deals if d["deal_status"] == "Dead"]
    elif 'hold' in query_lower:
        filtered = [d for d in deals if d["deal_status"] == "On Hold"]
    # Sector-specific filtering
    elif any(sector in query_lower for sector in ['mining', 'renewable', 'railway', 'power']):
        sector_keywords = {'mining': 'Mining', 'renewable': 'Renewables', 'railway': 'Railways', 'power': 'Powerline'}
        target_sector = next((v for k, v in sector_keywords.items() if k in query_lower), None)
        filtered = [d for d in deals if target_sector and target_sector in d["sector"]] if target_sector else deals
    # High-value filtering
    elif 'high' in query_lower or 'large' in query_lower or 'big' in query_lower:
        filtered = sorted(deals, key=lambda x: x["deal_value"], reverse=True)
    else:
        # Default: mix of statuses for overview
        filtered = deals
    
    # Return top deals with minimal fields to save tokens
    result = []
    for deal in filtered[:max_count]:
        result.append({
            "name": deal["deal_name"],
            "status": deal["deal_status"],
            "value": fmt_inr(deal["deal_value"]),
            "stage": deal["deal_stage"],
            "sector": deal["sector"],
            "owner": deal["owner_code"]
        })
    
    return result


def _filter_relevant_work_orders(work_orders: list, query: str, max_count: int = 10) -> list:
    """Filter work orders based on query context."""
    query_lower = query.lower()
    
    if 'ongoing' in query_lower or 'active' in query_lower:
        filtered = [w for w in work_orders if w["execution_status"] in ["Ongoing", "Active"]]
    elif 'completed' in query_lower:
        filtered = [w for w in work_orders if w["execution_status"] == "Completed"]
    elif 'billing' in query_lower or 'invoice' in query_lower:
        filtered = [w for w in work_orders if w["invoice_status"] != "Fully Billed"]
    else:
        filtered = work_orders
    
    # Return minimal fields
    result = []
    for wo in filtered[:max_count]:
        result.append({
            "name": wo["deal_name"],
            "status": wo["execution_status"],
            "sector": wo["sector"],
            "billed": fmt_inr(wo["billed_excl_gst"]),
            "receivable": fmt_inr(wo["amount_receivable"])
        })
    
    return result


# ─────────────────────────────────────────────
# TOKEN MANAGEMENT HELPERS
# ─────────────────────────────────────────────

def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters)."""
    return len(text) // 4

def truncate_response(data: dict, max_tokens: int = 15000) -> dict:
    """Truncate response data to stay within token limits."""
    response_text = json.dumps(data, default=str)
    estimated_tokens = estimate_tokens(response_text)
    
    if estimated_tokens <= max_tokens:
        return data
    
    # Progressive truncation strategy    
    if "sample_deals" in data and len(data["sample_deals"]) > 5:
        data["sample_deals"] = data["sample_deals"][:5]
        data["query_optimization"] += " (Truncated for token limits)"
    
    if "sample_work_orders" in data and len(data["sample_work_orders"]) > 5:
        data["sample_work_orders"] = data["sample_work_orders"][:5]
        data["query_optimization"] += " (Truncated for token limits)"
    
    return data


# ─────────────────────────────────────────────
# TOOL 1 — DEALS DATA
# ─────────────────────────────────────────────

@tool
def get_deals_data(query: str) -> str:
    """
    Fetches deals data from Monday.com with smart filtering to avoid token limits.

    Use this tool for any question about:
    - Pipeline health, deal counts, win rates
    - Revenue, deal values, forecasting
    - Deal stages (Lead → Won → Lost)
    - Sector-wise deal breakdown (Renewables, Mining, Railways, etc.)
    - Closure probability (High / Medium / Low)
    - Owner/sales rep performance
    - Deals created or closed in a specific time period
    - Open, Won, Dead, or On Hold deals

    Input: the user's original question as a string.
    Output: optimized JSON with summary stats and relevant deal samples.
    """
    try:
        logger.info("[DEALS] Tool called")
        logger.debug(f"[DEALS] Query: {query}")
        
        # Analyze query to determine response strategy
        query_lower = query.lower()
        needs_details = any(keyword in query_lower for keyword in [
            'list', 'show', 'details', 'which', 'who', 'name', 'specific'
        ])
        max_deals = 10 if needs_details else 3  # Limit deal examples
        
        # 1. Fetch live from Monday.com
        logger.info("[DEALS] Fetching from Monday.com...")
        raw_items = fetch_deals()
        logger.info(f"[DEALS] Raw items received: {len(raw_items)}")

        if not raw_items:
            logger.warning("[DEALS] No data returned from Monday.com")
            return json.dumps({
                "error": "No deals data returned from Monday.com. Board may be empty.",
                "deals": [],
                "summary": {}
            })

        # 2. Clean each row
        logger.info(f"[DEALS] Cleaning {len(raw_items)} rows...")
        cleaned = [clean_deal_row(row) for row in raw_items]
        logger.info(f"[DEALS] Cleaned: {len(cleaned)} rows")

        # 3. Filter out header rows (deal_stage is None)
        pre_filter = len(cleaned)
        cleaned = [d for d in cleaned if d.get("deal_stage") is not None]
        logger.info(f"[DEALS] After filtering null deal_stage: {len(cleaned)} (removed {pre_filter - len(cleaned)})")

        if not cleaned:
            logger.warning("[DEALS] All rows filtered out - deal_stage is null for all")
            return json.dumps({
                "error": "No valid deal data after processing. Check if deal_stage column is properly configured.",
                "raw_count": pre_filter,
                "cleaning_issue": "deal_stage column contains no values",
                "deals": [],
                "summary": {}
            })

        # 4. Build summary stats
        total = len(cleaned)
        won   = [d for d in cleaned if d["deal_status"] == "Won"]
        dead  = [d for d in cleaned if d["deal_status"] == "Dead"]
        open_ = [d for d in cleaned if d["deal_status"] == "Open"]
        hold  = [d for d in cleaned if d["deal_status"] == "On Hold"]

        logger.debug(f"[DEALS] Status breakdown - Won: {len(won)}, Dead: {len(dead)}, Open: {len(open_)}, Hold: {len(hold)}")

        total_value     = sum(d["deal_value"] for d in cleaned)
        won_value       = sum(d["deal_value"] for d in won)
        open_value      = sum(d["deal_value"] for d in open_)
        missing_value   = sum(1 for d in cleaned if d["deal_value"] == 0)

        logger.debug(f"[DEALS] Financial - Total: {total_value}, Won: {won_value}, Open: {open_value}")

        # Sector breakdown
        sector_counts = {}
        sector_values = {}
        for d in cleaned:
            s = d["sector"]
            sector_counts[s] = sector_counts.get(s, 0) + 1
            sector_values[s] = sector_values.get(s, 0.0) + d["deal_value"]

        # Stage breakdown
        stage_counts = {}
        for d in cleaned:
            st = d["deal_stage"]
            stage_counts[st] = stage_counts.get(st, 0) + 1

        # Owner breakdown
        owner_counts = {}
        for d in cleaned:
            o = d["owner_code"]
            owner_counts[o] = owner_counts.get(o, 0) + 1

        logger.info(f"[DEALS] Summary complete - {total} deals processed")

        summary = {
            "total_deals": total,
            "by_status": {
                "Won": len(won),
                "Dead": len(dead),
                "Open": len(open_),
                "On Hold": len(hold)
            },
            "financials": {
                "total_pipeline_value": fmt_inr(total_value),
                "won_value": fmt_inr(won_value),
                "open_pipeline_value": fmt_inr(open_value),
                "deals_missing_value": missing_value,
            },
            "by_sector": {
                s: {"count": sector_counts[s], "value": fmt_inr(sector_values[s])}
                for s in sorted(sector_counts, key=sector_counts.get, reverse=True)
            },
            "by_stage": dict(sorted(stage_counts.items(), key=lambda x: x[1], reverse=True)),
            "by_owner": dict(sorted(owner_counts.items(), key=lambda x: x[1], reverse=True)),
            "data_quality": get_data_quality_caveats(cleaned, "deals")
        }

        # Smart filtering based on query
        relevant_deals = _filter_relevant_deals(cleaned, query_lower, max_deals)
        
        # Estimate token usage and adjust
        response_data = {
            "summary": summary,
            "deals_count": len(cleaned),
            "sample_deals": relevant_deals,
            "query_optimization": f"Showing {len(relevant_deals)} most relevant deals out of {len(cleaned)} total"
        }
        
        # Apply token limits
        response_data = truncate_response(response_data)
        
        return json.dumps(response_data, default=str)

    except Exception as e:
        logger.error(f"[DEALS] Exception occurred: {str(e)}", exc_info=True)
        return json.dumps({
            "error": f"Failed to fetch deals data: {str(e)}",
            "deals": [],
            "summary": {}
        })


# ─────────────────────────────────────────────
# TOOL 2 — WORK ORDERS DATA
# ─────────────────────────────────────────────

@tool
def get_work_orders_data(query: str) -> str:
    """
    Fetches ALL work orders from the Monday.com Work Orders board via live API call.

    Use this tool for any question about:
    - Operational status (Completed, Ongoing, Not Started, Paused)
    - Billing and invoicing (Fully Billed, Partially Billed, Not Billed Yet)
    - Collections and receivables (Amount Receivable, Collected Amount)
    - Revenue from executed work (Amount Excl/Incl GST)
    - Sector-wise work order breakdown
    - Work order quantities (HA, KM, Acres, RKM)
    - Skylark software platform involvement (SPECTRA, DMO)
    - Specific work order by serial number or deal name
    - WO Status (Open / Closed)
    - AR Priority accounts

    Input: the user's original question as a string.
    Output: cleaned, structured JSON string of all work orders with summary stats.
    """
    try:
        # 1. Fetch live from Monday.com
        raw_items = fetch_work_orders()

        if not raw_items:
            return json.dumps({
                "error": "No work orders returned from Monday.com. Board may be empty.",
                "work_orders": [],
                "summary": {}
            })

        # 2. Clean each row
        cleaned = [clean_work_order_row(row) for row in raw_items]

        # 3. Build summary stats
        total = len(cleaned)

        # Execution status breakdown
        exec_counts = {}
        for w in cleaned:
            s = w["execution_status"]
            exec_counts[s] = exec_counts.get(s, 0) + 1

        # Financial totals
        total_contract     = sum(w["amount_excl_gst"] for w in cleaned)
        total_contract_gst = sum(w["amount_incl_gst"] for w in cleaned)
        total_billed       = sum(w["billed_excl_gst"] for w in cleaned)
        total_collected    = sum(w["collected_incl_gst"] for w in cleaned)
        total_to_bill      = sum(w["to_bill_excl_gst"] for w in cleaned)
        total_receivable   = sum(w["amount_receivable"] for w in cleaned)

        # Sector breakdown
        sector_counts = {}
        sector_values = {}
        for w in cleaned:
            s = w["sector"]
            sector_counts[s] = sector_counts.get(s, 0) + 1
            sector_values[s] = sector_values.get(s, 0.0) + w["amount_excl_gst"]

        # Invoice status breakdown
        invoice_counts = {}
        for w in cleaned:
            i = w["invoice_status"]
            invoice_counts[i] = invoice_counts.get(i, 0) + 1

        # WO status breakdown
        wo_status_counts = {}
        for w in cleaned:
            s = w["wo_status"]
            wo_status_counts[s] = wo_status_counts.get(s, 0) + 1

        # Software platform breakdown
        software_counts = {}
        for w in cleaned:
            s = w["software_platform"]
            software_counts[s] = software_counts.get(s, 0) + 1

        # AR Priority accounts
        priority_accounts = [
            w["deal_name"] for w in cleaned if w.get("ar_priority") == "Priority"
        ]

        summary = {
            "total_work_orders": total,
            "by_execution_status": dict(
                sorted(exec_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "financials": {
                "total_contract_value_excl_gst": fmt_inr(total_contract),
                "total_contract_value_incl_gst": fmt_inr(total_contract_gst),
                "total_billed_excl_gst":         fmt_inr(total_billed),
                "total_collected_incl_gst":       fmt_inr(total_collected),
                "total_amount_to_bill":           fmt_inr(total_to_bill),
                "total_amount_receivable":        fmt_inr(total_receivable),
            },
            "by_sector": {
                s: {"count": sector_counts[s], "value": fmt_inr(sector_values[s])}
                for s in sorted(sector_counts, key=sector_counts.get, reverse=True)
            },
            "by_invoice_status": dict(
                sorted(invoice_counts.items(), key=lambda x: x[1], reverse=True)
            ),
            "by_wo_status": wo_status_counts,
            "by_software_platform": software_counts,
            "ar_priority_accounts": priority_accounts,
            "data_quality": get_data_quality_caveats(cleaned, "work_orders")
        }

        # Query analysis for work orders
        query_lower = query.lower()
        needs_details = any(keyword in query_lower for keyword in [
            'list', 'show', 'details', 'which', 'who', 'name', 'specific'
        ])
        max_work_orders = 8 if needs_details else 3
        
        # Smart filtering
        relevant_work_orders = _filter_relevant_work_orders(cleaned, query_lower, max_work_orders)
        
        response_data = {
            "summary": summary,
            "work_orders_count": len(cleaned),
            "sample_work_orders": relevant_work_orders,
            "query_optimization": f"Showing {len(relevant_work_orders)} most relevant work orders out of {len(cleaned)} total"
        }

        # Apply token limits
        response_data = truncate_response(response_data)
        
        return json.dumps(response_data, default=str)

    except Exception as e:
        return json.dumps({
            "error": f"Failed to fetch work orders data: {str(e)}",
            "work_orders": [],
            "summary": {}
        })
