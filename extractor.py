"""
PDF invoice data extraction using pdfplumber.

Extracts: vendor name, invoice number, date, line items (description,
quantity, unit price, line total), subtotal, tax, shipping, total.

Strategy: try table extraction first (structured PDFs), fall back to
regex-based text parsing for messy/unstructured documents.
"""

import re
import pdfplumber


def extract_invoice(pdf_path: str) -> dict:
    """Extract structured data from an invoice PDF."""
    result = {
        "vendor_name": None,
        "invoice_number": None,
        "invoice_date": None,
        "line_items": [],
        "subtotal": None,
        "tax": None,
        "shipping": None,
        "total": None,
        "warnings": [],
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                result["error"] = "Empty PDF — no pages found."
                return result

            full_text = ""
            all_tables = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                full_text += text + "\n"
                tables = page.extract_tables() or []
                all_tables.extend(tables)

            if not full_text.strip():
                result["error"] = "Could not extract any text from PDF."
                result["warnings"].append("EMPTY_PDF")
                return result

            # Extract header fields
            result["vendor_name"] = _extract_vendor(full_text)
            result["invoice_number"] = _extract_invoice_number(full_text)
            result["invoice_date"] = _extract_date(full_text)

            # Extract line items (table first, text fallback)
            if all_tables:
                result["line_items"] = _extract_items_from_tables(all_tables)

            if not result["line_items"]:
                result["line_items"] = _extract_items_from_text(full_text)

            if not result["line_items"]:
                result["warnings"].append("NO_LINE_ITEMS_FOUND")

            # Extract totals
            result["subtotal"] = _extract_amount(full_text, r"[Ss]ub\s*[Tt]otal[:\s]*\$?([\d,.]+)")
            result["tax"] = _extract_amount(full_text, r"[Tt]ax[:\s]*\$?([\d,.]+)")
            result["shipping"] = _extract_amount(full_text, r"[Ss]hipping[:\s]*\$?([\d,.]+)")
            result["total"] = _extract_amount(full_text, r"(?:^|\n)\s*\**[Tt]otal\**[:\s]*\$?([\d,.]+)")

            if result["total"] is None:
                result["warnings"].append("MISSING_TOTAL")

    except Exception as e:
        result["error"] = f"Failed to process PDF: {str(e)}"

    return result


def _extract_vendor(text: str) -> str | None:
    """Extract vendor name from text."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # First, try explicit "Vendor:" label
    for line in lines:
        m = re.match(r"[Vv]endor[:\s]+(.+)", line)
        if m:
            name = m.group(1).strip()
            # Strip trailing address
            name = re.split(r"\s+\d+\s+\w+\s+(?:Rd|St|Ave|Blvd|Dr|Ln|Way|Ct|Pl|Pkwy)\b", name)[0]
            return name.strip()

    # Fallback: first non-header line
    for line in lines[:5]:
        if any(kw in line.lower() for kw in ["invoice", "date", "bill to", "ship to", "page"]):
            continue
        if len(line) > 3 and not line.startswith("$"):
            cleaned = re.split(r"\s+\d+\s+\w+\s+(?:Rd|St|Ave|Blvd|Dr|Ln|Way|Ct|Pl|Pkwy)\b", line)
            return cleaned[0].strip()
    return None


def _extract_invoice_number(text: str) -> str | None:
    """Extract invoice number."""
    patterns = [
        r"[Ii]nv(?:oice)?\s*(?:[Nn]o|#)\s*[:\s]*([A-Z0-9][\w-]+)",  # "Inv No: BO-8872" or "Invoice #: INV-1001"
        r"[Ii]nvoice\s*#?\s*:\s*([A-Z0-9][\w-]+)",                   # "Invoice: INV-1001"
        r"#\s*([A-Z]{2,}-\d+)",                                       # "#INV-1001"
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            val = m.group(1).strip()
            # Filter out false positives like "Copy"
            if val.lower() not in ("copy", "scanned", "draft", "page"):
                return val
    return None


def _extract_date(text: str) -> str | None:
    """Extract invoice date in various formats."""
    patterns = [
        r"[Dd]ate[:\s]*(\d{4}-\d{2}-\d{2})",
        r"[Dd]ate[:\s]*(\d{1,2}/\d{1,2}/\d{2,4})",
        r"[Dd]ate[:\s]*(\w+\s+\d{1,2},?\s+\d{4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_amount(text: str, pattern: str) -> float | None:
    """Extract a dollar amount using a regex pattern."""
    m = re.search(pattern, text, re.MULTILINE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_items_from_tables(tables: list) -> list[dict]:
    """Extract line items from pdfplumber table data."""
    items = []
    for table in tables:
        if not table or len(table) < 2:
            continue

        # Find header row
        header_idx = None
        for i, row in enumerate(table):
            row_text = " ".join(str(c or "").lower() for c in row)
            if any(kw in row_text for kw in ["description", "item", "qty", "quantity"]):
                header_idx = i
                break

        if header_idx is None:
            continue

        headers = [str(c or "").strip().lower() for c in table[header_idx]]

        # Map column indices
        desc_col = _find_col(headers, ["description", "item", "service", "product"])
        qty_col = _find_col(headers, ["qty", "quantity", "units"])
        price_col = _find_col(headers, ["unit price", "price", "rate", "unit cost"])
        total_col = _find_col(headers, ["total", "amount", "line total", "ext"])

        if desc_col is None:
            continue

        for row in table[header_idx + 1:]:
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue

            desc = str(row[desc_col] or "").strip() if desc_col < len(row) else ""
            if not desc or desc.lower() in ("subtotal", "total", "tax", "shipping"):
                continue

            item = {"description": desc}
            item["quantity"] = _parse_number(row[qty_col]) if qty_col is not None and qty_col < len(row) else None
            item["unit_price"] = _parse_number(row[price_col]) if price_col is not None and price_col < len(row) else None
            item["line_total"] = _parse_number(row[total_col]) if total_col is not None and total_col < len(row) else None

            # If we have qty and price but no total, calculate it
            if item["quantity"] and item["unit_price"] and not item["line_total"]:
                item["line_total"] = round(item["quantity"] * item["unit_price"], 2)

            items.append(item)

    return items


def _extract_items_from_text(text: str) -> list[dict]:
    """Fallback: extract line items from raw text using regex."""
    items = []
    # Pattern: description, qty, unit price, line total
    pattern = r"([A-Za-z][\w\s\(\)\-\+\.]+?)\s+(\d+(?:\.\d+)?)\s+\$?([\d,.]+)\s+\$?([\d,.]+)"
    for m in re.finditer(pattern, text):
        desc = m.group(1).strip()
        if desc.lower() in ("subtotal", "total", "tax", "shipping"):
            continue
        items.append({
            "description": desc,
            "quantity": _parse_number(m.group(2)),
            "unit_price": _parse_number(m.group(3)),
            "line_total": _parse_number(m.group(4)),
        })
    return items


def _find_col(headers: list[str], keywords: list[str]) -> int | None:
    """Find the column index that best matches the given keywords."""
    for i, h in enumerate(headers):
        for kw in keywords:
            if kw in h:
                return i
    return None


def _parse_number(value) -> float | None:
    """Parse a string/number into a float."""
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return None
