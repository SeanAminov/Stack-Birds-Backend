"""
Price comparison engine.

Compares invoice line items against per-vendor historical prices from the
Excel data. Falls back to the learning database if no static history exists.

Thresholds: 0.75x–1.5x of historical avg = acceptable. Outside = flag.
Tax and shipping are treated as observations, not hard gates.
"""

import math
from vendor_data import (
    PRICE_HISTORY, PRICE_RANGE_BUFFER,
    MAX_PRICE_RATIO_HIGH, MAX_PRICE_RATIO_LOW,
    VALID_TAX_RATES, TAX_TOLERANCE, SHIPPING_MAX_SEEN,
)
from matcher import normalize_item_name
from vendor_db import get_learned_rate


def _summarize_history(records: list[dict]) -> dict:
    """
    Summarize raw price history records into comparison-ready stats.

    Returns:
        n: number of data points
        min/max/avg: price stats
        avg_qty: average historical quantity
        prices: list of individual prices (for audit trail)
    """
    prices = [r["price"] for r in records]
    qtys = [r["qty"] for r in records if r.get("qty")]
    return {
        "n": len(prices),
        "min": min(prices),
        "max": max(prices),
        "avg": sum(prices) / len(prices),
        "avg_qty": sum(qtys) / len(qtys) if qtys else 1,
        "prices": prices,
    }


def _quantity_adjustment_factor(invoice_qty: float, historical_avg_qty: float) -> float:
    """
    Calculate a price adjustment factor based on quantity differences.

    Bulk orders naturally have lower unit prices. If someone orders 10x the
    usual quantity, we expect the unit price to be lower — that's a volume
    discount, not an error.

    Uses conservative log-based scaling:
    - qty_ratio = 2  → factor ~0.85  (expect ~15% cheaper)
    - qty_ratio = 5  → factor ~0.70  (expect ~30% cheaper)
    - qty_ratio = 10 → factor ~0.60  (expect ~40% cheaper)
    - qty_ratio = 0.5 → factor ~1.18 (expect ~18% more expensive)
    """
    if not invoice_qty or not historical_avg_qty or historical_avg_qty <= 0:
        return 1.0

    qty_ratio = invoice_qty / historical_avg_qty

    if 0.5 <= qty_ratio <= 2.0:
        return 1.0  # Roughly similar quantity — no adjustment

    adjustment = 1.0 / (1.0 + 0.25 * math.log2(max(qty_ratio, 0.1)))
    return max(0.4, min(2.0, adjustment))  # Clamp to reasonable bounds


def compare_line_items(vendor_name: str, line_items: list[dict]) -> list[dict]:
    """
    Compare each line item against historical price data for that vendor+item.

    Strict 0.75x–1.5x threshold, quantity-aware, with learning DB fallback.
    """
    results = []
    for item in line_items:
        canonical_item = normalize_item_name(item.get("description", ""))
        invoice_price = item.get("unit_price")
        invoice_qty = item.get("quantity") or 1

        # Look up price history: static data first, learning DB fallback
        history = PRICE_HISTORY.get((vendor_name, canonical_item))
        rate_source = "historical"
        rate_data = None

        if history:
            rate_data = _summarize_history(history)
        else:
            learned = get_learned_rate(vendor_name, canonical_item)
            if learned:
                rate_data = learned
                rate_source = "learned_db"

        result = {
            "description": item.get("description"),
            "canonical_item": canonical_item,
            "quantity": item.get("quantity"),
            "invoice_unit_price": invoice_price,
            "invoice_line_total": item.get("line_total"),
        }

        if rate_data is None:
            result.update({
                "contracted_range": None, "contracted_avg": None,
                "variance_from_avg_pct": None, "status": "NO_CONTRACT_RATE",
                "data_points": 0,
                "note": (
                    f"No historical rate data for '{canonical_item}' from {vendor_name}. "
                    f"Cannot compare — needs human review to establish baseline."
                ),
            })
        elif invoice_price is None:
            result.update({
                "contracted_range": f"${rate_data['min']:.2f} – ${rate_data['max']:.2f}",
                "contracted_avg": rate_data["avg"],
                "variance_from_avg_pct": None, "status": "MISSING_PRICE",
                "data_points": rate_data["n"],
                "note": "Invoice unit price could not be parsed from the document.",
            })
        else:
            n = rate_data["n"]

            # Buffer scales with sample size — less data = more buffer
            sample_buffer = PRICE_RANGE_BUFFER + max(0, (5 - n) * 0.10)

            # Quantity adjustment for bulk pricing
            hist_avg_qty = rate_data.get("avg_qty", 1)
            qty_factor = _quantity_adjustment_factor(invoice_qty, hist_avg_qty)

            adjusted_min = rate_data["min"] * (1 - sample_buffer) * qty_factor
            adjusted_max = rate_data["max"] * (1 + sample_buffer) * max(qty_factor, 1.0)
            adjusted_avg = rate_data["avg"] * qty_factor

            variance = ((invoice_price - adjusted_avg) / adjusted_avg) * 100 if adjusted_avg > 0 else 0

            # For display: show the actual range if multiple points, or single price
            if n == 1:
                range_display = f"${rate_data['min']:.2f} (1 data point)"
            else:
                range_display = f"${rate_data['min']:.2f} – ${rate_data['max']:.2f}"

            result.update({
                "contracted_range": range_display,
                "contracted_avg": rate_data["avg"],
                "variance_from_avg_pct": round(variance, 1),
                "data_points": n,
                "rate_source": rate_source,
                "qty_adjustment": round(qty_factor, 2) if qty_factor != 1.0 else None,
            })

            if adjusted_min <= invoice_price <= adjusted_max:
                result["status"] = "IN_RANGE"
                note = (
                    f"${invoice_price:.2f} is within acceptable range "
                    f"({range_display}, "
                    f"{n} data point{'s' if n > 1 else ''}, {sample_buffer*100:.0f}% buffer"
                )
                if qty_factor != 1.0:
                    note += f", qty-adjusted by {qty_factor:.2f}x"
                result["note"] = note + ")."
            else:
                direction = "below" if invoice_price < adjusted_min else "above"
                ratio = invoice_price / adjusted_avg if adjusted_avg > 0 else 999

                if ratio > MAX_PRICE_RATIO_HIGH or ratio < MAX_PRICE_RATIO_LOW:
                    result["status"] = "OUT_OF_RANGE"
                    if ratio > MAX_PRICE_RATIO_HIGH:
                        result["note"] = (
                            f"OVERPRICED: ${invoice_price:.2f} is {ratio:.1f}x the historical "
                            f"avg (${rate_data['avg']:.2f}). {range_display}. "
                            f"Exceeds {MAX_PRICE_RATIO_HIGH}x ceiling."
                        )
                    else:
                        result["note"] = (
                            f"UNDERPRICED: ${invoice_price:.2f} is {ratio:.2f}x the historical "
                            f"avg (${rate_data['avg']:.2f}). {range_display}. "
                            f"Below {MAX_PRICE_RATIO_LOW}x floor — "
                            f"possible error, wrong item, or missing quantity."
                        )
                else:
                    result["status"] = "OUTSIDE_RANGE"
                    pct = abs((invoice_price - (adjusted_min if direction == "below" else adjusted_max))
                              / (adjusted_min if direction == "below" else adjusted_max)) * 100
                    result["note"] = (
                        f"${invoice_price:.2f} is {direction} the historical range "
                        f"({range_display}, avg "
                        f"${rate_data['avg']:.2f}), {pct:.0f}% {direction} the buffered "
                        f"limit. Ratio: {ratio:.2f}x. Verify with vendor."
                    )

        results.append(result)
    return results


def check_math(line_items: list[dict], subtotal: float | None, tax: float | None,
               shipping: float | None, total: float | None) -> list[str]:
    """Verify internal math consistency. Hard check."""
    issues = []

    for item in line_items:
        qty = item.get("quantity")
        price = item.get("unit_price")
        line_total = item.get("line_total")
        if qty and price and line_total:
            expected = round(qty * price, 2)
            if abs(expected - line_total) > 0.50:
                issues.append(
                    f"Line math: {item.get('description')} — "
                    f"{qty} x ${price:.2f} = ${expected:.2f}, but invoice shows ${line_total:.2f}"
                )

    if subtotal is not None:
        line_sum = sum(i.get("line_total", 0) or 0 for i in line_items)
        if abs(line_sum - subtotal) > 1.00:
            issues.append(f"Subtotal: lines sum to ${line_sum:.2f}, invoice shows ${subtotal:.2f}")

    if total is not None and subtotal is not None:
        expected_total = subtotal + (tax or 0) + (shipping or 0)
        if abs(expected_total - total) > 1.00:
            issues.append(
                f"Total: ${subtotal:.2f} + tax(${tax or 0:.2f}) + shipping(${shipping or 0:.2f}) "
                f"= ${expected_total:.2f}, but invoice shows ${total:.2f}"
            )

    return issues


def check_tax(vendor_name: str, subtotal: float | None, tax: float | None) -> dict:
    """Observe tax. Returns observation, not pass/fail."""
    if subtotal is None or tax is None:
        return {"status": "OBSERVATION", "note": "Missing subtotal or tax value."}

    if tax == 0:
        return {
            "status": "OBSERVATION",
            "note": "No tax charged ($0). Could be tax-exempt or bundled into unit prices.",
        }

    effective_rate = tax / subtotal if subtotal > 0 else 0
    for valid_rate in VALID_TAX_RATES:
        if valid_rate > 0 and abs(effective_rate - valid_rate) <= TAX_TOLERANCE:
            return {
                "status": "OK",
                "effective_rate": round(effective_rate * 100, 2),
                "note": f"Tax rate {effective_rate*100:.2f}% matches known rate {valid_rate*100:.1f}%.",
            }

    valid_strs = ", ".join(f"{r*100:.1f}%" for r in VALID_TAX_RATES if r > 0)
    return {
        "status": "OBSERVATION",
        "effective_rate": round(effective_rate * 100, 2),
        "note": f"Tax rate {effective_rate*100:.2f}% doesn't match known rates ({valid_strs}).",
    }


def check_shipping(vendor_name: str, shipping: float | None) -> dict:
    """Observe shipping. Lenient — varies by distance/weight."""
    max_seen = SHIPPING_MAX_SEEN.get(vendor_name)

    if shipping is None:
        return {"status": "OBSERVATION", "note": "No shipping field found."}
    if shipping == 0:
        return {"status": "OK", "note": "No shipping charged."}
    if max_seen is None:
        return {"status": "OBSERVATION", "note": f"Shipping ${shipping:.2f}. No history to compare."}
    if shipping <= max_seen:
        return {"status": "OK", "note": f"Shipping ${shipping:.2f} within norms (max seen: ${max_seen:.2f})."}

    return {
        "status": "OBSERVATION",
        "note": f"Shipping ${shipping:.2f} above max seen (${max_seen:.2f}). Could be distance/rush.",
    }
