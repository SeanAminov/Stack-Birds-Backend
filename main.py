"""
Invoice Processing Agent — Main Entry Point

7-step pipeline: extract PDF -> match vendor -> compare prices -> policy
checks -> decision + questions -> LLM analysis -> generate reports.

Usage:
    python main.py                           # Process all in ./invoices/
    python main.py path/to/invoice.pdf       # Process a single file
"""

import sys
import os
from extractor import extract_invoice
from matcher import match_vendor
from comparator import compare_line_items, check_math, check_tax, check_shipping
from decision import decide
from analyzer import analyze_invoice, get_analyzer_status
from report import build_json_payload, build_reconciliation_report, build_audit_trail, save_outputs
from vendor_db import record_invoice, get_db_stats


def process_invoice(pdf_path: str, output_dir: str = "output") -> dict:
    """Run the full 7-step pipeline on a single invoice PDF."""
    invoice_name = os.path.splitext(os.path.basename(pdf_path))[0]
    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path}")
    print(f"{'='*60}")

    # Step 1: Extract
    print("  [1/7] Extracting invoice data...")
    invoice_data = extract_invoice(pdf_path)

    if invoice_data.get("error"):
        print(f"  ERROR: {invoice_data['error']}")
        return invoice_data

    print(f"        Vendor: {invoice_data.get('vendor_name', '?')}")
    print(f"        Invoice #: {invoice_data.get('invoice_number', '?')}")
    print(f"        Line items: {len(invoice_data.get('line_items', []))}")
    if invoice_data.get("warnings"):
        print(f"        Warnings: {', '.join(invoice_data['warnings'])}")

    # Step 2: Match vendor
    print("  [2/7] Matching vendor...")
    vendor_match = match_vendor(invoice_data.get("vendor_name"))
    canonical_vendor = vendor_match.get("canonical_name")
    print(f"        Match: {canonical_vendor} ({vendor_match['match_type']}, "
          f"{vendor_match['confidence']*100:.0f}%)")

    # Step 3: Compare rates
    print("  [3/7] Comparing rates (contracted + learning DB)...")
    line_comparisons = compare_line_items(
        canonical_vendor or "",
        invoice_data.get("line_items", []),
    )
    in_range = sum(1 for c in line_comparisons if c["status"] == "IN_RANGE")
    outside = sum(1 for c in line_comparisons if c["status"] == "OUTSIDE_RANGE")
    outlier = sum(1 for c in line_comparisons if c["status"] == "OUT_OF_RANGE")
    no_rate = sum(1 for c in line_comparisons if c["status"] == "NO_CONTRACT_RATE")
    from_db = sum(1 for c in line_comparisons if c.get("rate_source") == "learned_db")
    print(f"        In range: {in_range}, Outside: {outside}, Flagged: {outlier}, No data: {no_rate}")
    if from_db:
        print(f"        ({from_db} item(s) compared via learning database)")

    # Step 4: Policy checks
    print("  [4/7] Running policy checks...")
    math_issues = check_math(
        invoice_data.get("line_items", []),
        invoice_data.get("subtotal"),
        invoice_data.get("tax"),
        invoice_data.get("shipping"),
        invoice_data.get("total"),
    )
    tax_check = check_tax(canonical_vendor or "", invoice_data.get("subtotal"), invoice_data.get("tax"))
    shipping_check = check_shipping(canonical_vendor or "", invoice_data.get("shipping"))

    if math_issues:
        print(f"        Math issues: {len(math_issues)}")
    print(f"        Tax: {tax_check['status']}")
    print(f"        Shipping: {shipping_check['status']}")

    # Step 5: Decision (ALWAYS includes clarifying questions)
    print("  [5/7] Making decision...")
    decision_result = decide(
        vendor_match, line_comparisons, math_issues,
        tax_check, shipping_check, invoice_data.get("warnings", []),
    )
    print(f"        >>> {decision_result['status']} <<<")
    if decision_result["reason_codes"]:
        for reason in decision_result["reason_codes"]:
            print(f"            - {reason}")
    for i, q in enumerate(decision_result.get("clarifying_questions", []), 1):
        print(f"        Q{i}: {q[:80]}...")

    # Step 6: LLM Analysis (autonomous reasoning with constraints)
    print("  [6/7] Running LLM analysis...")
    db_stats = get_db_stats()
    ai_analysis = analyze_invoice(
        invoice_data, vendor_match, line_comparisons,
        math_issues, tax_check, shipping_check,
        decision_result, db_stats,
    )

    if ai_analysis.get("ai_available"):
        print(f"        AI Risk Level: {ai_analysis['risk_level'].upper()}")
        print(f"        AI Summary: {ai_analysis['executive_summary'][:80]}...")
        if ai_analysis.get("insights"):
            for insight in ai_analysis["insights"][:2]:
                print(f"        Insight: {insight[:75]}...")
        if ai_analysis.get("recommended_questions"):
            for i, q in enumerate(ai_analysis["recommended_questions"], 1):
                print(f"        AI Q{i}: {q[:75]}...")
        print(f"        Model: {ai_analysis['model']} ({ai_analysis['latency_ms']}ms)")
    else:
        print(f"        LLM unavailable — {ai_analysis.get('explanation', 'no details')}")
        print(f"        (Deterministic results are complete — LLM adds depth, not requirements)")

    # Step 7: Generate outputs
    print("  [7/7] Generating reports...")
    json_payload = build_json_payload(
        invoice_data, vendor_match, line_comparisons,
        math_issues, tax_check, shipping_check, decision_result,
        ai_analysis,
    )
    report = build_reconciliation_report(
        invoice_data, vendor_match, line_comparisons,
        math_issues, tax_check, shipping_check, decision_result,
        ai_analysis,
    )
    audit = build_audit_trail(
        invoice_data, vendor_match, line_comparisons,
        math_issues, tax_check, shipping_check, decision_result,
        ai_analysis,
    )

    save_outputs(invoice_name, json_payload, report, audit, output_dir)

    # Record approved invoices for future baselines
    record_invoice(invoice_data, decision_result["status"], canonical_vendor or "")
    if decision_result["status"] == "APPROVED":
        print(f"        Recorded to learning DB for future baselines.")

    return json_payload


def main():
    # Show analyzer status at startup
    analyzer_status = get_analyzer_status()
    if analyzer_status["available"]:
        print(f"LLM Analyzer: ACTIVE (model: {analyzer_status['model']})")
        print(f"  Guardrails: {len(analyzer_status['guardrails'])} active constraints")
    else:
        reasons = []
        if not analyzer_status["openai_package"]:
            reasons.append("openai package not installed")
        if not analyzer_status["api_key_set"]:
            reasons.append("OPENAI_API_KEY not set")
        print(f"LLM Analyzer: INACTIVE ({', '.join(reasons)})")
        print(f"  System runs fully on deterministic rules — LLM is optional depth.")

    if len(sys.argv) > 1:
        for path in sys.argv[1:]:
            if os.path.isfile(path):
                process_invoice(path)
            else:
                print(f"File not found: {path}")
    else:
        invoices_dir = os.path.join(os.path.dirname(__file__) or ".", "invoices")
        if not os.path.isdir(invoices_dir):
            print(f"No invoices directory found at {invoices_dir}")
            print("Usage: python main.py [invoice.pdf ...]")
            sys.exit(1)

        pdfs = sorted(f for f in os.listdir(invoices_dir) if f.lower().endswith(".pdf"))
        if not pdfs:
            print(f"No PDF files found in {invoices_dir}")
            sys.exit(1)

        print(f"\nFound {len(pdfs)} invoice(s) to process.\n")
        results = []
        for pdf in pdfs:
            result = process_invoice(os.path.join(invoices_dir, pdf))
            results.append(result)

        # Summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        approved = sum(1 for r in results if r.get("status") == "APPROVED")
        flagged = sum(1 for r in results if r.get("status") == "FLAGGED")
        print(f"  Processed: {len(results)}")
        print(f"  Approved:  {approved}")
        print(f"  Flagged:   {flagged}")

        db_stats = get_db_stats()
        print(f"\n  Learning DB: {db_stats['total_invoices']} invoices, "
              f"{db_stats['unique_vendors']} vendors, "
              f"{db_stats['unique_items_tracked']} items tracked")

        if analyzer_status["available"]:
            risk_levels = [r.get("ai_analysis", {}).get("risk_level", "N/A") for r in results]
            print(f"  AI Risk Levels: {', '.join(risk_levels)}")

        print(f"\nAll outputs saved to ./output/")


if __name__ == "__main__":
    main()
