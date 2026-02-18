"""
Vendor and item name matching.

Matching pipeline (in order of confidence):
  1. Exact match against canonical vendor names
  2. Alias match against known aliases (case-insensitive)
  3. Fuzzy match using thefuzz (Levenshtein distance)

Item names go through a normalization step to handle OCR artifacts
and abbreviations ("Cable Mgmt Kit" -> "Cable Management Kit").
"""

import re
from thefuzz import fuzz
from vendor_data import APPROVED_VENDORS, ITEM_ALIASES


def match_vendor(invoice_vendor_name: str | None) -> dict:
    """
    Match an invoice vendor name against the approved vendor list.

    Returns:
        canonical_name: The official vendor name (or None)
        match_type: "exact", "alias", "fuzzy", "fuzzy_low_confidence", or "none"
        confidence: 0.0 to 1.0
    """
    if not invoice_vendor_name:
        return {"canonical_name": None, "match_type": "none", "confidence": 0.0}

    name = invoice_vendor_name.strip()
    name_lower = name.lower()

    # 1. Exact match
    for canonical in APPROVED_VENDORS:
        if name == canonical or name_lower == canonical.lower():
            return {"canonical_name": canonical, "match_type": "exact", "confidence": 1.0}

    # 2. Alias match
    for canonical, aliases in APPROVED_VENDORS.items():
        if name_lower in aliases:
            return {"canonical_name": canonical, "match_type": "alias", "confidence": 0.95}

    # 3. Fuzzy match
    best_score = 0
    best_match = None
    for canonical, aliases in APPROVED_VENDORS.items():
        # Check against canonical name
        score = fuzz.ratio(name_lower, canonical.lower())
        if score > best_score:
            best_score = score
            best_match = canonical

        # Check against each alias
        for alias in aliases:
            score = fuzz.ratio(name_lower, alias)
            if score > best_score:
                best_score = score
                best_match = canonical

    if best_score >= 85:
        return {"canonical_name": best_match, "match_type": "fuzzy", "confidence": best_score / 100}
    elif best_score >= 60:
        return {"canonical_name": best_match, "match_type": "fuzzy_low_confidence", "confidence": best_score / 100}

    return {"canonical_name": None, "match_type": "none", "confidence": 0.0}


def normalize_item_name(description: str) -> str:
    """
    Normalize an item description to its canonical form.

    Handles OCR artifacts, abbreviations, and trailing context
    like "Standing Desk Rental - Nov" -> "Standing Desk Rental".
    """
    if not description:
        return description

    cleaned = description.strip()
    cleaned_lower = cleaned.lower()

    # Direct alias lookup
    if cleaned_lower in ITEM_ALIASES:
        return ITEM_ALIASES[cleaned_lower]

    # Try stripping trailing context (dates, notes)
    stripped = re.sub(r"\s*[-–]\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec).*$",
                      "", cleaned_lower, flags=re.IGNORECASE)
    if stripped in ITEM_ALIASES:
        return ITEM_ALIASES[stripped]

    # Try common abbreviation expansions
    expanded = cleaned_lower
    expanded = expanded.replace("mgmt", "management")
    expanded = expanded.replace("maint", "maintenance")
    expanded = expanded.replace("equip", "equipment")
    if expanded in ITEM_ALIASES:
        return ITEM_ALIASES[expanded]

    # Return original with title case as best effort
    return cleaned
