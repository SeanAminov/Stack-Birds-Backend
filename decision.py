"""
Decision engine — produces a flag AND clarifying questions for every invoice.

Every invoice gets: a status (APPROVED/FLAGGED), reason codes, observations,
and 1-3 clarifying questions. Even approved invoices get a sanity-check
question — no invoice passes without at least one human checkpoint.
"""


def decide(vendor_match: dict, line_comparisons: list[dict], math_issues: list[str],
           tax_check: dict, shipping_check: dict, extraction_warnings: list[str]) -> dict:
    """
    Make an approve/flag decision with BOTH flags AND clarifying questions.

    Returns:
        status: "APPROVED" or "FLAGGED"
        reason_codes: list of machine-readable reasons for flagging
        observations: list of human-readable notes
        clarifying_questions: 1-3 questions (ALWAYS present, even for APPROVED)
    """
    flags = []
    observations = []
    questions = []

    # ── VENDOR CHECK (hard gate) ─────────────────────────────────────
    if vendor_match["match_type"] == "none":
        flags.append("VENDOR_NOT_IN_APPROVED_LIST")
        questions.append(
            "This vendor is not in our approved vendor list. "
            "Is this a new vendor that needs onboarding, or a known vendor under a different name?"
        )
    elif vendor_match["match_type"] == "fuzzy_low_confidence":
        flags.append("VENDOR_LOW_CONFIDENCE_MATCH")
        questions.append(
            f"Vendor matched to '{vendor_match['canonical_name']}' with only "
            f"{vendor_match['confidence']*100:.0f}% confidence. Is this correct?"
        )
    elif vendor_match["match_type"] == "fuzzy":
        observations.append(
            f"Vendor fuzzy-matched to '{vendor_match['canonical_name']}' "
            f"({vendor_match['confidence']*100:.0f}% confidence)."
        )
    elif vendor_match["match_type"] == "alias":
        observations.append(
            f"Vendor matched via known alias to '{vendor_match['canonical_name']}'."
        )

    # ── LINE ITEM PRICE CHECKS ──────────────────────────────────────
    items_no_rate = []
    items_out_of_range = []
    items_outside_range = []

    for comp in line_comparisons:
        if comp["status"] == "NO_CONTRACT_RATE":
            items_no_rate.append(comp)
        elif comp["status"] == "OUT_OF_RANGE":
            items_out_of_range.append(comp)
        elif comp["status"] == "OUTSIDE_RANGE":
            items_outside_range.append(comp)
        elif comp["status"] == "MISSING_PRICE":
            flags.append(f"MISSING_PRICE:{comp['canonical_item']}")

    # No rate history
    if items_no_rate:
        names = [c["canonical_item"] for c in items_no_rate]
        if vendor_match["match_type"] == "none":
            flags.append("VENDOR_NOT_IN_APPROVED_LIST")
            _assess_unknown_items(items_no_rate, observations, questions)
        else:
            flags.append(f"NEW_ITEMS_NO_RATE_HISTORY:{', '.join(names)}")
            questions.append(
                f"No historical pricing for: {', '.join(names)}. "
                f"Are these new products/services from this vendor? "
                f"If approved, these prices become the baseline for future invoices."
            )

    # Hard flag: beyond 1.5x/0.75x threshold
    if items_out_of_range:
        for comp in items_out_of_range:
            flags.append(f"PRICE_ANOMALY:{comp['canonical_item']}")
        details = [
            f"{c['canonical_item']} (${c['invoice_unit_price']:.2f} vs avg "
            f"${c['contracted_avg']:.2f} — {c['note'].split(':')[0]})"
            for c in items_out_of_range
        ]
        questions.append(
            f"Price anomalies beyond the 1.5x/0.75x threshold: {'; '.join(details)}. "
            f"Please verify these prices with the vendor before approving."
        )

    # Soft flag: outside range but within threshold
    if items_outside_range:
        for comp in items_outside_range:
            flags.append(f"PRICE_OUTSIDE_RANGE:{comp['canonical_item']}")
        details = [
            f"{c['canonical_item']} (${c['invoice_unit_price']:.2f} vs "
            f"{c['contracted_range']})"
            for c in items_outside_range
        ]

        # Pattern detection: ALL items outside range = systemic issue
        total_priced = sum(
            1 for c in line_comparisons
            if c["status"] not in ("MISSING_PRICE", "NO_CONTRACT_RATE")
        )
        all_outside = (len(items_outside_range) + len(items_out_of_range)) == total_priced and total_priced > 1

        if all_outside:
            questions.append(
                "Every line item is priced outside the historical range. "
                "Has there been a contract renegotiation or pricing restructure?"
            )
        observations.append(f"Price variance: {'; '.join(details)}. Verify with vendor.")

    # ── MATH CHECK (hard gate) ───────────────────────────────────────
    if math_issues:
        flags.append("MATH_DISCREPANCY")
        for issue in math_issues:
            observations.append(f"Math issue: {issue}")
        questions.append(
            "The invoice math doesn't add up. Is this a rounding issue, "
            "or could there be a missing line item or incorrect amount?"
        )

    # ── TAX & SHIPPING (observations) ────────────────────────────────
    if tax_check["status"] == "OBSERVATION":
        observations.append(f"Tax: {tax_check['note']}")
    elif tax_check["status"] == "OK":
        observations.append(f"Tax: {tax_check['note']}")

    if shipping_check["status"] == "OBSERVATION":
        observations.append(f"Shipping: {shipping_check['note']}")
    elif shipping_check["status"] == "OK":
        observations.append(f"Shipping: {shipping_check['note']}")

    # ── EXTRACTION QUALITY ───────────────────────────────────────────
    critical = [w for w in extraction_warnings if w in ("NO_LINE_ITEMS_FOUND", "EMPTY_PDF", "MISSING_TOTAL")]
    if critical:
        flags.append(f"EXTRACTION_FAILURE:{', '.join(critical)}")
    non_critical = [w for w in extraction_warnings if w not in critical]
    if non_critical:
        observations.append(f"Extraction notes: {', '.join(non_critical)}")

    # ── FINAL DECISION ───────────────────────────────────────────────
    status = "APPROVED" if len(flags) == 0 else "FLAGGED"

    # ALWAYS generate at least one clarifying question, even for approved
    # invoices. This is the supervision layer — no invoice goes through
    # without at least one human checkpoint question.
    if not questions:
        questions.append(
            "This invoice passed all automated checks. Please confirm the "
            "quantities and descriptions match what was actually received "
            "before final approval."
        )

    # Cap at 3 questions — more than that is overwhelming for a reviewer
    questions = questions[:3]

    return {
        "status": status,
        "reason_codes": flags,
        "observations": observations,
        "clarifying_questions": questions,
    }


def _assess_unknown_items(items: list[dict], observations: list[str], questions: list[str]):
    """Sanity-check prices for unknown vendors."""
    reasonable = []
    concerning = []

    for comp in items:
        price = comp.get("invoice_unit_price")
        name = comp["canonical_item"]
        if price is None:
            concerning.append(name)
        elif 1.0 <= price <= 1000.0:
            reasonable.append(f"{name} (${price:.2f})")
        else:
            concerning.append(f"{name} (${price:.2f})")

    if reasonable:
        observations.append(f"Prices appear reasonable: {', '.join(reasonable)}.")
    if concerning:
        observations.append(f"Unusual pricing — needs review: {', '.join(concerning)}.")

    questions.append(
        "This vendor has no invoice history. Is this a first-time order? "
        "Please confirm the prices match the agreed contract terms."
    )
