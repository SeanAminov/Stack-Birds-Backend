"""
Report generation — three outputs per invoice:
  1. Structured JSON payload
  2. Human-readable reconciliation report
  3. Audit trail
"""

import json
from datetime import datetime, timezone


def build_json_payload(invoice_data: dict, vendor_match: dict, line_comparisons: list[dict],
                       math_issues: list[str], tax_check: dict, shipping_check: dict,
                       decision_result: dict, ai_analysis: dict = None) -> dict:
    """Build the structured decision payload."""
    has_variance = any(
        c["status"] in ("OUT_OF_RANGE", "OUTSIDE_RANGE", "NO_CONTRACT_RATE", "MISSING_PRICE")
        for c in line_comparisons
    )

    payload = {
        "invoice_number": invoice_data.get("invoice_number"),
        "vendor_name_on_invoice": invoice_data.get("vendor_name"),
        "matched_vendor": vendor_match.get("canonical_name"),
        "vendor_match_confidence": vendor_match.get("confidence"),
        "invoice_date": invoice_data.get("invoice_date"),
        "invoice_total": invoice_data.get("total"),
        "status": decision_result["status"],
        "variance_detected": has_variance,
        "reason_codes": decision_result["reason_codes"],
        "clarifying_questions": decision_result.get("clarifying_questions", []),
        "reconciliation_summary": {
            "line_items_checked": len(line_comparisons),
            "items_in_range": sum(1 for c in line_comparisons if c["status"] == "IN_RANGE"),
            "items_outside_range": sum(1 for c in line_comparisons if c["status"] == "OUTSIDE_RANGE"),
            "items_out_of_range": sum(1 for c in line_comparisons if c["status"] == "OUT_OF_RANGE"),
            "items_no_contract": sum(1 for c in line_comparisons if c["status"] == "NO_CONTRACT_RATE"),
            "math_issues": len(math_issues),
            "tax_status": tax_check["status"],
            "shipping_status": shipping_check["status"],
        },
    }

    # AI analysis section — clearly labeled as advisory
    if ai_analysis:
        payload["ai_analysis"] = {
            "available": ai_analysis.get("ai_available", False),
            "model": ai_analysis.get("model"),
            "risk_level": ai_analysis.get("risk_level"),
            "executive_summary": ai_analysis.get("executive_summary"),
            "insights": ai_analysis.get("insights", []),
            "recommended_questions": ai_analysis.get("recommended_questions", []),
            "explanation": ai_analysis.get("explanation"),
            "latency_ms": ai_analysis.get("latency_ms", 0),
            "note": "AI analysis is ADVISORY. Algorithmic flags are final and cannot be overridden by AI.",
        }

    return payload


def build_reconciliation_report(invoice_data: dict, vendor_match: dict,
                                line_comparisons: list[dict], math_issues: list[str],
                                tax_check: dict, shipping_check: dict,
                                decision_result: dict, ai_analysis: dict = None) -> str:
    """Build a human-readable reconciliation report."""
    lines = []
    sep = "=" * 72

    lines.append(sep)
    lines.append("  INVOICE RECONCILIATION REPORT")
    lines.append(sep)
    lines.append("")
    lines.append(f"  Invoice:     {invoice_data.get('invoice_number', 'N/A')}")
    lines.append(f"  Vendor:      {invoice_data.get('vendor_name', 'N/A')}")
    lines.append(f"  Matched to:  {vendor_match.get('canonical_name', 'UNRECOGNIZED')} "
                 f"({vendor_match.get('match_type', 'N/A')}, "
                 f"{vendor_match.get('confidence', 0)*100:.0f}% confidence)")
    lines.append(f"  Date:        {invoice_data.get('invoice_date', 'N/A')}")
    lines.append(f"  Total:       ${invoice_data.get('total', 0) or 0:,.2f}")
    lines.append("")

    status = decision_result["status"]
    if status == "APPROVED":
        lines.append(f"  Decision:    >>> APPROVED <<<")
    else:
        lines.append(f"  Decision:    >>> FLAGGED FOR HUMAN REVIEW <<<")
    if decision_result["reason_codes"]:
        lines.append(f"  Reasons:     {', '.join(decision_result['reason_codes'])}")
    lines.append("")

    # Line-by-line comparison
    lines.append("-" * 72)
    lines.append("  LINE ITEM COMPARISON")
    lines.append("-" * 72)
    lines.append(f"  {'Item':<26} {'Qty':>5} {'Invoice$':>10} {'Range (historical)':>22} {'Status'}")
    lines.append(f"  {'-'*24}  {'-'*5} {'-'*10} {'-'*22} {'-'*12}")

    for comp in line_comparisons:
        name = (comp.get("canonical_item") or "?")[:24]
        qty = comp.get("quantity") or "?"
        inv_price = f"${comp['invoice_unit_price']:.2f}" if comp.get("invoice_unit_price") is not None else "N/A"
        contracted = comp.get("contracted_range") or "No data"
        status_sym = {
            "IN_RANGE":          "OK",
            "OUTSIDE_RANGE":     "! OUTSIDE",
            "OUT_OF_RANGE":      "!! FLAG",
            "NO_CONTRACT_RATE":  "? NEW",
            "MISSING_PRICE":     "? MISSING",
        }.get(comp["status"], comp["status"])

        lines.append(f"  {name:<26} {str(qty):>5} {inv_price:>10} {contracted:>22} {status_sym}")

    lines.append("")

    # Totals
    lines.append("-" * 72)
    lines.append("  TOTALS & OBSERVATIONS")
    lines.append("-" * 72)
    lines.append(f"  Subtotal:  ${invoice_data.get('subtotal', 0) or 0:,.2f}")
    lines.append(f"  Tax:       ${invoice_data.get('tax', 0) or 0:,.2f}")
    lines.append(f"  Shipping:  ${invoice_data.get('shipping', 0) or 0:,.2f}")
    lines.append(f"  Total:     ${invoice_data.get('total', 0) or 0:,.2f}")

    if math_issues:
        lines.append("")
        lines.append("  Math Issues:")
        for issue in math_issues:
            lines.append(f"    !! {issue}")

    if decision_result.get("observations"):
        lines.append("")
        lines.append("-" * 72)
        lines.append("  OBSERVATIONS")
        lines.append("-" * 72)
        for obs in decision_result["observations"]:
            lines.append(f"  - {obs}")

    # Clarifying questions (ALWAYS present)
    if decision_result.get("clarifying_questions"):
        lines.append("")
        lines.append("-" * 72)
        lines.append("  CLARIFYING QUESTIONS (for human reviewer)")
        lines.append("-" * 72)
        for i, q in enumerate(decision_result["clarifying_questions"], 1):
            lines.append(f"  Q{i}: {q}")

    # AI Analysis section
    if ai_analysis and ai_analysis.get("ai_available"):
        lines.append("")
        lines.append("-" * 72)
        lines.append("  AI ANALYSIS (advisory — algorithmic flags are final)")
        lines.append("-" * 72)
        lines.append(f"  Risk Level:  {ai_analysis.get('risk_level', 'N/A').upper()}")
        lines.append(f"  Summary:     {ai_analysis.get('executive_summary', 'N/A')}")
        lines.append("")

        if ai_analysis.get("insights"):
            lines.append("  Insights:")
            for insight in ai_analysis["insights"]:
                lines.append(f"    - {insight}")
            lines.append("")

        if ai_analysis.get("recommended_questions"):
            lines.append("  AI-Generated Questions:")
            for i, q in enumerate(ai_analysis["recommended_questions"], 1):
                lines.append(f"    AQ{i}: {q}")
            lines.append("")

        if ai_analysis.get("explanation"):
            lines.append(f"  Explanation: {ai_analysis['explanation']}")

        lines.append(f"  Model: {ai_analysis.get('model', 'N/A')} | "
                     f"Latency: {ai_analysis.get('latency_ms', 0)}ms")
    elif ai_analysis and not ai_analysis.get("ai_available"):
        lines.append("")
        lines.append("-" * 72)
        lines.append("  AI ANALYSIS: unavailable")
        lines.append("-" * 72)
        lines.append(f"  {ai_analysis.get('explanation', 'LLM not configured.')}")
        lines.append("  Deterministic analysis above is complete — AI adds depth, not requirements.")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def build_audit_trail(invoice_data: dict, vendor_match: dict, line_comparisons: list[dict],
                      math_issues: list[str], tax_check: dict, shipping_check: dict,
                      decision_result: dict, ai_analysis: dict = None) -> str:
    """Build a detailed audit trail log."""
    entries = []
    ts = datetime.now(timezone.utc).isoformat()

    entries.append(f"[{ts}] AUDIT TRAIL - Invoice {invoice_data.get('invoice_number', 'UNKNOWN')}")
    entries.append("")

    # Step 1: Extraction
    entries.append("STEP 1: DATA EXTRACTION")
    entries.append(f"  Source: PDF file")
    entries.append(f"  Vendor extracted: '{invoice_data.get('vendor_name', 'N/A')}'")
    entries.append(f"  Invoice #: {invoice_data.get('invoice_number', 'N/A')}")
    entries.append(f"  Date: {invoice_data.get('invoice_date', 'N/A')}")
    entries.append(f"  Line items found: {len(invoice_data.get('line_items', []))}")
    entries.append(f"  Subtotal: ${invoice_data.get('subtotal', 'N/A')}")
    entries.append(f"  Tax: ${invoice_data.get('tax', 'N/A')}")
    entries.append(f"  Shipping: ${invoice_data.get('shipping', 'N/A')}")
    entries.append(f"  Total: ${invoice_data.get('total', 'N/A')}")
    if invoice_data.get("warnings"):
        entries.append(f"  Extraction warnings: {', '.join(invoice_data['warnings'])}")
    else:
        entries.append("  Extraction warnings: None")
    entries.append("")

    # Step 2: Vendor matching
    entries.append("STEP 2: VENDOR VERIFICATION")
    entries.append(f"  Invoice says: '{invoice_data.get('vendor_name', 'N/A')}'")
    entries.append(f"  Best match: '{vendor_match.get('canonical_name', 'NONE')}'")
    entries.append(f"  Match method: {vendor_match.get('match_type', 'N/A')}")
    entries.append(f"  Confidence: {vendor_match.get('confidence', 0)*100:.0f}%")
    if vendor_match["match_type"] == "alias":
        entries.append(f"  ASSUMPTION: Known alias for '{vendor_match['canonical_name']}'.")
    elif vendor_match["match_type"] in ("fuzzy", "fuzzy_low_confidence"):
        entries.append(f"  UNCERTAINTY: Fuzzy match — needs human confirmation.")
    elif vendor_match["match_type"] == "none":
        entries.append(f"  UNCERTAINTY: Vendor not in approved list.")
    entries.append("")

    # Step 3: Rate comparison
    entries.append("STEP 3: PRICE COMPARISON (0.75x-1.5x threshold, qty-aware)")
    for comp in line_comparisons:
        entries.append(f"  Item: {comp.get('canonical_item', '?')}")
        entries.append(f"    Invoice price: ${comp.get('invoice_unit_price', 'N/A')}")
        entries.append(f"    Quantity: {comp.get('quantity', 'N/A')}")
        entries.append(f"    Historical range: {comp.get('contracted_range', 'No data')}")
        entries.append(f"    Avg from history: ${comp.get('contracted_avg', 'N/A')}")
        entries.append(f"    Variance from avg: {comp.get('variance_from_avg_pct', 'N/A')}%")
        if comp.get("rate_source"):
            entries.append(f"    Rate source: {comp['rate_source']}")
        if comp.get("qty_adjustment"):
            entries.append(f"    Qty adjustment: {comp['qty_adjustment']}x")
        entries.append(f"    Verdict: {comp.get('status', 'N/A')}")
        entries.append(f"    Detail: {comp.get('note', '')}")
    entries.append("")

    # Step 4: Policy checks
    entries.append("STEP 4: MATH, TAX & SHIPPING CHECKS")
    if math_issues:
        entries.append(f"  Math: {len(math_issues)} issue(s)")
        for issue in math_issues:
            entries.append(f"    - {issue}")
    else:
        entries.append("  Math: All calculations verified.")
    entries.append(f"  Tax: {tax_check.get('note', 'N/A')}")
    entries.append(f"  Shipping: {shipping_check.get('note', 'N/A')}")
    entries.append("")

    # Step 5: Decision
    entries.append("STEP 5: ALGORITHMIC DECISION")
    entries.append(f"  Status: {decision_result['status']}")
    entries.append("")

    if decision_result["reason_codes"]:
        entries.append("  FLAG REASONS:")
        for reason in decision_result["reason_codes"]:
            entries.append(f"    - {reason}")
        entries.append("")

    if decision_result.get("observations"):
        entries.append("  OBSERVATIONS:")
        for obs in decision_result["observations"]:
            entries.append(f"    - {obs}")
        entries.append("")

    if decision_result.get("clarifying_questions"):
        entries.append("  CLARIFYING QUESTIONS:")
        for i, q in enumerate(decision_result["clarifying_questions"], 1):
            entries.append(f"    Q{i}: {q}")
        entries.append("")

    entries.append("  REASONING:")
    if decision_result["status"] == "APPROVED":
        entries.append("    Vendor recognized, prices within historical range (0.75x-1.5x),")
        entries.append("    math verified, tax/shipping normal. However, a clarifying question")
        entries.append("    has been generated for human review — no invoice is auto-approved")
        entries.append("    without at least one supervision checkpoint.")
    else:
        entries.append("    One or more checks produced a flag requiring human attention.")
        entries.append("    This does NOT mean the invoice is wrong — it means the system")
        entries.append("    cannot confidently verify it. See clarifying questions above.")
    entries.append("")

    # Step 6: AI Analysis
    entries.append("STEP 6: AI ANALYSIS (advisory layer)")
    if ai_analysis and ai_analysis.get("ai_available"):
        entries.append(f"  Model: {ai_analysis.get('model', 'N/A')}")
        entries.append(f"  Latency: {ai_analysis.get('latency_ms', 0)}ms")
        entries.append(f"  Risk Level: {ai_analysis.get('risk_level', 'N/A').upper()}")
        entries.append(f"  Executive Summary: {ai_analysis.get('executive_summary', 'N/A')}")
        entries.append("")

        if ai_analysis.get("insights"):
            entries.append("  AI INSIGHTS:")
            for insight in ai_analysis["insights"]:
                entries.append(f"    - {insight}")
            entries.append("")

        if ai_analysis.get("recommended_questions"):
            entries.append("  AI-GENERATED QUESTIONS:")
            for i, q in enumerate(ai_analysis["recommended_questions"], 1):
                entries.append(f"    AQ{i}: {q}")
            entries.append("")

        if ai_analysis.get("explanation"):
            entries.append(f"  AI EXPLANATION: {ai_analysis['explanation']}")
            entries.append("")

        entries.append("  GUARDRAIL STATUS:")
        entries.append("    - AI cannot override algorithmic flags: ENFORCED")
        entries.append("    - AI cannot approve FLAGGED invoices: ENFORCED")
        entries.append("    - AI risk_level validated against algorithmic status: ENFORCED")
        entries.append("    - All AI outputs sanitized and truncated: ENFORCED")
    elif ai_analysis:
        entries.append(f"  Status: UNAVAILABLE")
        entries.append(f"  Reason: {ai_analysis.get('explanation', 'Not configured')}")
        entries.append("  Note: Deterministic analysis is complete. AI is an optional depth layer.")
    else:
        entries.append("  Status: NOT RUN")
    entries.append("")

    entries.append("GUARDRAIL SUMMARY:")
    entries.append("  Algorithmic decision is FINAL — AI analysis is advisory only.")
    entries.append("  AI cannot weaken, override, or modify any algorithmic flags.")
    entries.append("  If AI and algorithm disagree, the algorithm always wins.")

    return "\n".join(entries)


def save_outputs(invoice_name: str, json_payload: dict, report: str, audit: str, output_dir: str = "output"):
    """Save all three outputs to files."""
    import os
    os.makedirs(output_dir, exist_ok=True)

    base = os.path.join(output_dir, invoice_name)

    with open(f"{base}_decision.json", "w") as f:
        json.dump(json_payload, f, indent=2)

    with open(f"{base}_report.txt", "w") as f:
        f.write(report)

    with open(f"{base}_audit.txt", "w") as f:
        f.write(audit)

    print(f"  Saved: {base}_decision.json")
    print(f"  Saved: {base}_report.txt")
    print(f"  Saved: {base}_audit.txt")
