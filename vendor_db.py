"""
Learning database — stores approved invoice history as future baselines.

When a human approves an invoice, its prices get saved here. Next time
the same vendor+item appears, we have something to compare against.
Deterministic, auditable, and gets smarter with every approval.

Storage: ./data/invoice_history.json (auto-created)
"""

import json
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__) or ".", "data", "invoice_history.json")


def _load_db() -> dict:
    """Load database from disk, or create empty structure."""
    if os.path.exists(DB_PATH):
        with open(DB_PATH, "r") as f:
            return json.load(f)
    return {
        "metadata": {
            "created": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
        },
        "invoices": [],
        "price_history": {},
    }


def _save_db(db: dict):
    """Save database to disk."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


def record_invoice(invoice_data: dict, decision_status: str, vendor_name: str):
    """
    Record an approved invoice to build future baselines.
    Only learns from APPROVED invoices — flagged prices don't pollute baselines.
    """
    if decision_status != "APPROVED":
        return

    db = _load_db()
    invoice_id = invoice_data.get("invoice_number", "UNKNOWN")

    # Don't record duplicates
    if invoice_id in {inv.get("invoice_number") for inv in db["invoices"]}:
        return

    db["invoices"].append({
        "invoice_number": invoice_id,
        "vendor": vendor_name,
        "date": invoice_data.get("invoice_date"),
        "total": invoice_data.get("total"),
        "tax": invoice_data.get("tax"),
        "shipping": invoice_data.get("shipping"),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    })

    for item in invoice_data.get("line_items", []):
        desc = item.get("description", "").strip()
        if not desc:
            continue

        key = f"{vendor_name}|{desc}"
        if key not in db["price_history"]:
            db["price_history"][key] = []

        db["price_history"][key].append({
            "unit_price": item.get("unit_price"),
            "quantity": item.get("quantity"),
            "line_total": item.get("line_total"),
            "date": invoice_data.get("invoice_date"),
            "invoice_id": invoice_id,
        })

    _save_db(db)


def get_learned_rate(vendor_name: str, item_name: str) -> dict | None:
    """
    Look up historical pricing from the learning database.
    Returns rate_data dict compatible with CONTRACTED_RATES, or None.
    """
    db = _load_db()
    key = f"{vendor_name}|{item_name}"
    history = db.get("price_history", {}).get(key, [])

    if not history:
        return None

    prices = [h["unit_price"] for h in history if h.get("unit_price") is not None]
    qtys = [h["quantity"] for h in history if h.get("quantity") is not None]

    if not prices:
        return None

    return {
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
        "n": len(prices),
        "avg_qty": sum(qtys) / len(qtys) if qtys else 1,
        "source": "learned_db",
    }


def get_db_stats() -> dict:
    """High-level stats about the learning database."""
    db = _load_db()
    vendors = set(inv.get("vendor") for inv in db["invoices"])
    return {
        "total_invoices": len(db["invoices"]),
        "unique_vendors": len(vendors),
        "unique_items_tracked": len(db.get("price_history", {})),
        "db_path": DB_PATH,
    }
