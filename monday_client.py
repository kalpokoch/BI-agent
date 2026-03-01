
import requests
import json
import logging
from config import (
    MONDAY_API_KEY,
    MONDAY_API_URL,
    MONDAY_API_VERSION,
    DEALS_BOARD_ID,
    WORK_ORDERS_BOARD_ID,
    DEALS_COLUMNS,
    WO_COLUMNS
)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# ─────────────────────────────────────────────
# BASE REQUEST HANDLER
# ─────────────────────────────────────────────

def _run_query(query: str) -> dict:
    """
    Execute a GraphQL query against Monday.com API.
    Raises RuntimeError on HTTP or API-level errors.
    """
    logger.debug(f"[API] Running query: {query[:200]}...")
    
    if not MONDAY_API_KEY:
        raise RuntimeError("MONDAY_API_KEY is not set in environment variables")
    
    headers = {
        "Authorization": MONDAY_API_KEY,
        "API-Version": MONDAY_API_VERSION,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            MONDAY_API_URL,
            json={"query": query},
            headers=headers,
            timeout=30
        )
        logger.debug(f"[API] Response status: {response.status_code}")
    except requests.exceptions.Timeout:
        logger.error("[API] Request timed out")
        raise RuntimeError("Monday.com API request timed out. Please try again.")
    except requests.exceptions.ConnectionError:
        logger.error("[API] Connection error")
        raise RuntimeError("Could not connect to Monday.com API. Check your internet connection.")

    if response.status_code == 401:
        logger.error("[API] Authentication failed - check MONDAY_API_KEY")
        raise RuntimeError("Monday.com API authentication failed. Check your MONDAY_API_KEY in .env")

    if response.status_code != 200:
        logger.error(f"[API] HTTP {response.status_code}: {response.text}")
        raise RuntimeError(f"Monday.com API returned HTTP {response.status_code}: {response.text}")

    data = response.json()

    if "errors" in data:
        error_msg = data["errors"][0].get("message", "Unknown API error")
        logger.error(f"[API] API Error: {error_msg}")
        raise RuntimeError(f"Monday.com API error: {error_msg}")

    logger.debug(f"[API] Query successful")
    return data


# ─────────────────────────────────────────────
# ITEM PARSER
# ─────────────────────────────────────────────

def _parse_items(items: list, column_map: dict) -> list:
    """
    Convert raw Monday.com items into clean dicts
    using column_map to assign meaningful key names.
    column_map: {friendly_name: column_id}
    """
    logger.debug(f"[PARSE] Parsing {len(items)} items")
    # Invert map: {column_id: friendly_name}
    id_to_key = {v: k for k, v in column_map.items()}
    logger.debug(f"[PARSE] Column mapping - {len(id_to_key)} columns")

    parsed = []
    for idx, item in enumerate(items):
        row = {"id": item["id"]}

        # Item name field
        row["deal_name"] = item.get("name", "")

        # All other column values
        for col in item.get("column_values", []):
            col_id = col["id"]
            if col_id in id_to_key:
                key = id_to_key[col_id]
                # Use 'text' for human-readable value
                # Use 'value' for raw JSON (dropdowns, status)
                text_val = col.get("text", "") or ""
                row[key] = text_val.strip() if text_val else None

        parsed.append(row)
        
        if idx == 0:
            logger.debug(f"[PARSE] Sample parsed item: {row}")

    logger.debug(f"[PARSE] Completed parsing - {len(parsed)} items")
    return parsed


# ─────────────────────────────────────────────
# PAGINATED FETCH
# ─────────────────────────────────────────────

def _fetch_all_items(board_id: str, column_map: dict) -> list:
    """
    Fetch ALL items from a board using cursor-based pagination.
    Monday.com returns max 500 items per page.
    Keeps fetching until no more pages remain.
    """
    logger.info(f"[FETCH] Starting fetch from board {board_id}")
    logger.debug(f"[FETCH] Column map: {list(column_map.keys())}")
    
    if not board_id:
        logger.error("[FETCH] Board ID is missing!")
        raise RuntimeError("Board ID is not configured")
    
    all_items = []
    cursor = None
    page = 1

    # Build column IDs string for GraphQL
    col_ids = json.dumps(list(column_map.values()))

    while True:
        if cursor:
            items_query = f'items_page(limit: 500, cursor: "{cursor}")'
        else:
            items_query = "items_page(limit: 500)"

        query = """
        {
          boards(ids: %s) {
            %s {
              cursor
              items {
                id
                name
                column_values(ids: %s) {
                  id
                  text
                  value
                }
              }
            }
          }
        }
        """ % (board_id, items_query, col_ids)

        data = _run_query(query)
        
        try:
            board_data = data["data"]["boards"][0]["items_page"]
        except (KeyError, IndexError) as e:
            logger.error(f"[FETCH] Failed to parse response: {data}")
            raise RuntimeError(f"Failed to parse Monday.com response: {str(e)}")
        
        items = board_data.get("items", [])
        cursor = board_data.get("cursor")
        
        logger.info(f"[FETCH] Page {page}: Retrieved {len(items)} items (cursor: {cursor is not None})")
        page += 1

        parsed = _parse_items(items, column_map)
        all_items.extend(parsed)

        # No more pages
        if not cursor or len(items) == 0:
            logger.info(f"[FETCH] Pagination complete. Total items: {len(all_items)}")
            break

    return all_items


# ─────────────────────────────────────────────
# PUBLIC API — DEALS
# ─────────────────────────────────────────────

def fetch_deals() -> list:
    """
    Fetch all items from the Deals board (live, no cache).
    Returns list of cleaned deal dicts.
    """
    return _fetch_all_items(DEALS_BOARD_ID, DEALS_COLUMNS)


# ─────────────────────────────────────────────
# PUBLIC API — WORK ORDERS
# ─────────────────────────────────────────────

def fetch_work_orders() -> list:
    """
    Fetch all items from the Work Orders board (live, no cache).
    Returns list of cleaned work order dicts.
    """
    return _fetch_all_items(WORK_ORDERS_BOARD_ID, WO_COLUMNS)


# ─────────────────────────────────────────────
# BOARD HEALTH CHECK
# ─────────────────────────────────────────────

def check_boards_accessible() -> dict:
    """
    Lightweight check to verify both boards are reachable.
    Used by validate_env() at startup.
    Returns {"deals": True/False, "work_orders": True/False}
    """
    results = {}

    for name, board_id in [("deals", DEALS_BOARD_ID), ("work_orders", WORK_ORDERS_BOARD_ID)]:
        query = """
        {
          boards(ids: %s) {
            id
            name
          }
        }
        """ % board_id

        try:
            data = _run_query(query)
            boards = data["data"]["boards"]
            results[name] = len(boards) > 0
        except Exception:
            results[name] = False

    return results
