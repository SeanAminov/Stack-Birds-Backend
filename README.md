# Invoice Processing Agent

**Stackbirds Backend Spring Internship 2026**

A supervision-first invoice processing system with an LLM-powered analysis layer. It extracts data from PDF invoices, verifies vendors against an approved list, compares prices against per-vendor historical data, runs autonomous AI analysis with strict guardrails, and produces decisions with full explainability. Every invoice gets both a clear flag AND clarifying questions -- no invoice passes without human oversight.

---

## Architecture

```
PDF Invoice
    |
    v
[1. EXTRACTOR]   ----> pdfplumber: table extraction + regex text fallback
    |
    v
[2. MATCHER]     ----> Vendor lookup: exact -> alias -> fuzzy (thefuzz)
    |
    v
[3. COMPARATOR]  ----> Price check: per-vendor historical range + qty-aware bulk logic
    |                   Fallback: learning database for new vendors
    |                   Math: qty x price = line total, subtotal + tax + ship = total
    |                   Tax/shipping: observation-only, never auto-reject
    |
    v
[4. DECISION]    ----> ALWAYS produces: flag + reason codes + clarifying questions
    |
    v
[5. ANALYZER]    ----> LLM (gpt-4o-mini) with STRICT guardrails
    |                   Can ADD insights/questions, CANNOT override flags
    |                   Timeout + fallback: system works without it
    |
    v
[6. REPORTER]    ----> 3 outputs: JSON payload, reconciliation report, audit trail
    |
    v
[7. LEARNING DB] ----> Records approved invoices for future baselines
```

**9 modules, single responsibility each:**

| Module | Role |
|--------|------|
| `main.py` | CLI entry point, 7-step pipeline |
| `extractor.py` | PDF parsing (pdfplumber tables + regex fallback) |
| `matcher.py` | Vendor/item name matching (exact, alias, fuzzy) |
| `comparator.py` | Price comparison (per-vendor ranges, qty-aware, 0.75x-1.5x threshold) |
| `decision.py` | Flag + clarifying questions engine (ALWAYS both) |
| `analyzer.py` | LLM analysis with strict guardrails (advisory only) |
| `report.py` | JSON payload, reconciliation report, audit trail |
| `vendor_data.py` | Static reference data (verified line-by-line from Excel) |
| `vendor_db.py` | Learning database (JSON-backed, builds baselines from approved invoices) |

**Key design decisions:**

- **Supervision, not automation.** Every invoice gets 1-3 clarifying questions, even approved ones. The system surfaces the right questions for a human reviewer -- it does not replace human judgment.
- **Per-vendor price history.** Acme's Staples Pack at $28-$148 comes from Acme's 3 invoices only. No cross-vendor averaging. All rates verified line-by-line from the source Excel file.
- **Quantity-aware pricing.** If historical avg quantity is 150 chairs at $39/ea and the invoice has 2 chairs at $90/ea, that is a legitimate small-order premium, not an anomaly. Log-based adjustment prevents false flags on bulk/small order differences.
- **LLM as advisory layer, not decision-maker.** The AI adds depth (insights, explanations, smarter questions) but CANNOT override algorithmic flags. If the math says 2.8x overpriced, no AI reasoning can change that. Guardrails enforced in code, not just prompts.
- **Learning database as institutional memory.** JSON-backed database that learns from approved invoices. First Zenith invoice = no history = flagged. Human approves = prices recorded. Second Zenith invoice = baseline exists. Deterministic, auditable, zero cost.
- **Strict 0.75x-1.5x threshold.** Any price above 1.5x or below 0.75x the historical average (after quantity adjustment) is hard-flagged as OVERPRICED or UNDERPRICED.

---

## The LLM Analyzer

### Why an LLM on Top of Algorithms?

The deterministic system (comparator + decision engine) handles the math: price ranges, thresholds, quantity adjustments. It's reliable and auditable, but it can't reason about _context_.

The LLM adds:
- **Plain English explanations** — "This toner is 2.8x the avg because..." instead of just "OUT_OF_RANGE"
- **Pattern detection** — "All 3 items from this vendor are overpriced — possible contract renegotiation"
- **Smarter questions** — Context-aware clarifying questions beyond what rules can generate
- **Risk assessment** — Overall risk level (low/medium/high/critical) considering all factors together

### Strict Guardrails (enforced in code, not prompts)

| Guardrail | How It's Enforced |
|-----------|-------------------|
| LLM cannot override flags | `decision.py` runs first, flags are FINAL. LLM sees flags as read-only input. |
| LLM cannot approve flagged invoices | `_validate_and_sanitize()` — if algorithm says FLAGGED, AI risk_level cannot be "low" |
| Structured output only | `response_format={"type": "json_object"}` — free text rejected |
| Output validation | Every field is type-checked, truncated, and clamped to valid ranges |
| Timeout protection | 15s hard timeout — if LLM hangs, system produces results without it |
| Retry with fallback | 1 retry, then graceful degradation to deterministic-only |
| No data fabrication | LLM receives structured results, not raw PDFs. Can't invent numbers. |
| Audit trail | All AI outputs tagged as "advisory" in every output format |

### How It Works in Practice

```
WITHOUT API KEY (fully functional):
  Algorithm runs → Decision made → Reports generated
  AI section says: "LLM unavailable — deterministic results only"

WITH API KEY:
  Algorithm runs → Decision made → LLM analyzes → Reports include AI section
  AI section adds: risk level, insights, smarter questions, explanation
  But: algorithmic flags are UNCHANGED. AI is depth, not authority.
```

---

## Setup & Usage

### Prerequisites
- Python 3.10+
- (Optional) OpenAI API key for LLM analysis

### Install

```bash
git clone https://github.com/SeanAminov/Stack-Birds-Backend.git
cd Stack-Birds-Backend
pip install -r requirements.txt
```

### Configure LLM (optional)

Create a `.env` file in the project root:

```
OPENAI_API_KEY=sk-your-key-here
```

Or set the environment variable directly:

```bash
# Windows
set OPENAI_API_KEY=sk-your-key-here

# Mac/Linux
export OPENAI_API_KEY=sk-your-key-here
```

The system works fully without an API key — the LLM layer is optional depth.

### Run

```bash
python main.py                        # Process all PDFs in ./invoices/
python main.py path/to/invoice.pdf    # Process a single file
```

### Verify

1. Run `python main.py`
2. Check console: all 3 invoices should be FLAGGED with specific reasons
3. If API key is set: AI analysis appears with risk levels, insights, and questions
4. If no API key: system runs fully on deterministic rules
5. Open `output/` to see the 3 output files per invoice

---

## System Outputs

### 1. Structured Decision Payload (JSON)

```json
{
  "invoice_number": "INV-1001",
  "vendor_name_on_invoice": "Acme Supplies Inc.",
  "matched_vendor": "Acme Supplies Inc.",
  "vendor_match_confidence": 1.0,
  "invoice_date": "2025-11-02",
  "invoice_total": 1302.35,
  "status": "FLAGGED",
  "variance_detected": true,
  "reason_codes": [
    "PRICE_ANOMALY:Printer Toner Model X",
    "PRICE_ANOMALY:Staples Pack"
  ],
  "clarifying_questions": [
    "Price anomalies beyond the 1.5x/0.75x threshold..."
  ],
  "reconciliation_summary": {
    "line_items_checked": 3,
    "items_in_range": 1,
    "items_out_of_range": 2,
    "math_issues": 0,
    "tax_status": "OK",
    "shipping_status": "OK"
  },
  "ai_analysis": {
    "available": true,
    "model": "gpt-4o-mini",
    "risk_level": "high",
    "executive_summary": "Significant price anomalies detected...",
    "insights": ["Toner at 2.8x suggests possible billing error..."],
    "recommended_questions": ["Was there a recent price change for toner?"],
    "explanation": "Two of three items have extreme variance...",
    "note": "AI analysis is ADVISORY. Algorithmic flags are final."
  }
}
```

### 2. Human-Readable Reconciliation Report

```
========================================================================
  INVOICE RECONCILIATION REPORT
========================================================================

  Invoice:     INV-1001
  Vendor:      Acme Supplies Inc.
  Decision:    >>> FLAGGED FOR HUMAN REVIEW <<<

------------------------------------------------------------------------
  LINE ITEM COMPARISON
------------------------------------------------------------------------
  Item                         Qty   Invoice$     Range (historical) Status
  A4 Paper Box                20.0     $25.00        $24.19 - $88.72 OK
  Printer Toner Model X        5.0    $120.00        $15.09 - $32.61 !! FLAG
  Staples Pack                10.0      $8.00       $28.43 - $147.86 !! FLAG

------------------------------------------------------------------------
  CLARIFYING QUESTIONS (for human reviewer)
------------------------------------------------------------------------
  Q1: Verify these prices with the vendor before approving.

------------------------------------------------------------------------
  AI ANALYSIS (advisory — algorithmic flags are final)
------------------------------------------------------------------------
  Risk Level:  HIGH
  Summary:     Significant price anomalies on 2 of 3 line items...
  Insights:
    - Toner at $120 is 2.8x the historical average of $21.20
    - Staples at $8 is 0.06x the average — possible wrong item
  AI-Generated Questions:
    AQ1: Was there a recent price change for Printer Toner Model X?
========================================================================
```

### 3. Audit Trail

```
STEP 1: DATA EXTRACTION
  Vendor extracted: 'Acme Supplies Inc.'

STEP 3: PRICE COMPARISON (0.75x-1.5x threshold, qty-aware)
  Item: Printer Toner Model X
    Invoice price: $120.0
    Historical range: $15.09 - $32.61 (Acme-only, 3 data points)
    Verdict: OUT_OF_RANGE

STEP 5: ALGORITHMIC DECISION
  Status: FLAGGED

STEP 6: AI ANALYSIS (advisory layer)
  Model: gpt-4o-mini
  Risk Level: HIGH
  GUARDRAIL STATUS:
    - AI cannot override algorithmic flags: ENFORCED
    - AI cannot approve FLAGGED invoices: ENFORCED
    - All AI outputs sanitized and truncated: ENFORCED

GUARDRAIL SUMMARY:
  Algorithmic decision is FINAL — AI analysis is advisory only.
```

---

## Example Results

| Invoice | Vendor | Status | Flags | AI Risk | Key Question |
|---------|--------|--------|-------|---------|-------------|
| INV-1001 (clean) | Acme Supplies | FLAGGED | Toner OVERPRICED (2.8x), Staples UNDERPRICED (0.06x) | HIGH | Verify prices with vendor |
| BO-8872 (messy) | BrightOffice | FLAGGED | Cable Kit UNDERPRICED (0.28x) | MEDIUM | Verify price with vendor |
| ZCG-5541 (edge) | Zenith Catering | FLAGGED | No rate history for any items | MEDIUM | First-time order? Confirm contract terms |

**Note on the messy invoice:** The Standing Desk ($150, qty=1) and Ergonomic Chair ($90, qty=2) both pass because the historical data shows avg quantities of 122 and 150 respectively. Ordering 1-2 units when the norm is 100+ means a small-order premium is expected. The system's quantity-aware pricing correctly identifies this as normal.

---

## The Learning Database

```
First Zenith invoice  -->  No history  -->  FLAGGED + "Is this a first-time order?"
                                               |
                              Human approves   |
                                               v
                           Prices saved to data/invoice_history.json
                                               |
Second Zenith invoice -->  Has baseline  -->  Compared against learned rates
                                               |
                           Within 0.75x-1.5x   -->  APPROVED (still gets a question)
                           Outside threshold    -->  FLAGGED
```

The learning database IS the institutional memory. It replaces brute-force LLM pattern recognition with something auditable and deterministic for price baselines, while the LLM layer handles the reasoning and context that algorithms can't.

---

## Top 5 Risks and Mitigations

### 1. LLM Hallucination / False Confidence
**Risk:** The LLM could generate plausible-sounding but incorrect analysis, giving a human reviewer false confidence in an approval or flag.

**Mitigation:** Strict guardrails enforced in code (not prompts). LLM cannot override algorithmic flags. All AI output is type-validated, truncated, and labeled as "advisory." The audit trail explicitly marks guardrail enforcement status. Temperature set to 0.1 for deterministic responses.

### 2. PDF Extraction Failures
**Risk:** pdfplumber can not parse every format. Scanned images, unusual layouts, or damaged files fail or produce garbage data.

**Mitigation:** The system tracks extraction warnings and flags invoices missing critical fields. For production: add OCR (Tesseract/AWS Textract) as fallback, and score extraction confidence.

### 3. Historical Data Poisoning
**Risk:** If a fraudulent invoice is accidentally approved, its inflated prices enter the learning database and shift the baseline. Future similar invoices would pass.

**Mitigation:** Only APPROVED invoices are recorded (human-reviewed). Add a periodic audit that flags statistical outliers in the database. Require N>3 data points before learned baselines are used for comparison.

### 4. Vendor Name Spoofing
**Risk:** A malicious actor submits an invoice from "Acme Suppliess Inc." (typo). The fuzzy matcher could match it to real "Acme Supplies Inc." at high confidence, bypassing vendor checks.

**Mitigation:** Fuzzy matches below 85% are flagged. For production: cross-reference vendor bank account details and PO numbers, not just names. Add a blocklist for known spoofing patterns.

### 5. Quantity Manipulation
**Risk:** Someone inflates quantities to justify high totals while keeping unit prices in range. Billing for 1000 pens at $70/box when only 10 were delivered.

**Mitigation:** The system verifies math but not whether quantities are reasonable vs. what was ordered. For production: cross-reference against purchase orders or delivery receipts, flag quantities 5x+ the historical average.

---

## Project Structure

```
Stack-Birds-Backend/
  main.py              # CLI entry point (7-step pipeline)
  extractor.py         # PDF data extraction (pdfplumber)
  matcher.py           # Vendor + item name matching (thefuzz)
  comparator.py        # Price comparison (per-vendor, qty-aware)
  decision.py          # Flag + clarifying questions (ALWAYS both)
  analyzer.py          # LLM analysis with strict guardrails (advisory)
  report.py            # Output generation (JSON, report, audit)
  vendor_data.py       # Static reference data (verified from Excel)
  vendor_db.py         # Learning database (JSON-backed)
  requirements.txt     # Dependencies
  .env                 # API key (optional, not committed)
  invoices/            # Input PDF invoices
  output/              # Generated reports
  data/                # Learning DB storage (auto-created)
```
