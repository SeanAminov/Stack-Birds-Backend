"""
LLM-powered analysis layer that sits on top of the deterministic system.

The algorithm runs first and produces flags. The LLM then receives those
structured results and adds: plain English explanations, pattern detection,
smarter clarifying questions, and risk assessment.

Key constraint: the LLM can never override or weaken algorithmic flags.
Guardrails are enforced in code (_validate_and_sanitize), not just prompts.
If the LLM is unavailable, the system works fine without it.

Requires: OPENAI_API_KEY in environment or .env file.
"""

import json
import os
import time
from typing import Optional

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import openai
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# ── Configuration ─────────────────────────────────────────────────
MODEL = "gpt-4o-mini"
MAX_TOKENS = 800
TEMPERATURE = 0.1          # Low temperature = deterministic, less creative
TIMEOUT_SECONDS = 15        # Hard timeout — system works without LLM
MAX_RETRIES = 1

# ── Guardrail Constants ──────────────────────────────────────────
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}
MAX_INSIGHTS = 5
MAX_QUESTIONS = 3
MAX_EXPLANATION_LEN = 500


def _get_client() -> Optional["OpenAI"]:
    """Get OpenAI client if API key is available."""
    if not OPENAI_AVAILABLE:
        return None
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def _build_system_prompt() -> str:
    """System prompt with strict constraints baked in."""
    return """You are an invoice analysis assistant embedded in a deterministic invoice processing system.

STRICT CONSTRAINTS — YOU CANNOT VIOLATE THESE:
1. You CANNOT approve, override, or weaken any flags from the deterministic system.
2. You CANNOT change the status from FLAGGED to APPROVED.
3. You CANNOT ignore price anomalies — if the system says 2.8x, it IS 2.8x.
4. You CANNOT invent prices, rates, or data points that aren't in the input.
5. Your role is ADVISORY — you add depth, explanations, and smarter questions.

YOUR JOB:
- Explain WHY flagged items are concerning in plain business English
- Identify patterns (e.g., "all items from this vendor are overpriced" = possible contract issue)
- Generate 1-3 specific, actionable clarifying questions for the human reviewer
- Assess overall risk level: low / medium / high / critical
- Surface anything the algorithm might miss (unusual combinations, timing, context)

OUTPUT FORMAT — respond ONLY with valid JSON, no markdown, no explanation outside the JSON:
{
  "risk_level": "low|medium|high|critical",
  "executive_summary": "1-2 sentence plain English summary of the invoice",
  "insights": ["insight 1", "insight 2"],
  "recommended_questions": ["question 1", "question 2"],
  "explanation": "Plain English explanation of why this invoice was flagged (or why it passed)"
}"""


def _build_user_prompt(invoice_data: dict, vendor_match: dict,
                       line_comparisons: list[dict], math_issues: list[str],
                       tax_check: dict, shipping_check: dict,
                       decision_result: dict, db_stats: dict) -> str:
    """Build the structured context for the LLM — no raw PDF content."""
    context = {
        "invoice": {
            "number": invoice_data.get("invoice_number"),
            "vendor_on_invoice": invoice_data.get("vendor_name"),
            "matched_vendor": vendor_match.get("canonical_name"),
            "vendor_match_type": vendor_match.get("match_type"),
            "vendor_confidence": vendor_match.get("confidence"),
            "date": invoice_data.get("invoice_date"),
            "subtotal": invoice_data.get("subtotal"),
            "tax": invoice_data.get("tax"),
            "shipping": invoice_data.get("shipping"),
            "total": invoice_data.get("total"),
        },
        "line_items": [],
        "algorithmic_decision": {
            "status": decision_result["status"],
            "reason_codes": decision_result["reason_codes"],
            "observations": decision_result["observations"],
        },
        "math_issues": math_issues,
        "tax_check": tax_check,
        "shipping_check": shipping_check,
        "learning_db_stats": db_stats,
    }

    for comp in line_comparisons:
        context["line_items"].append({
            "item": comp.get("canonical_item"),
            "quantity": comp.get("quantity"),
            "invoice_price": comp.get("invoice_unit_price"),
            "historical_range": comp.get("contracted_range"),
            "historical_avg": comp.get("contracted_avg"),
            "variance_pct": comp.get("variance_from_avg_pct"),
            "qty_adjustment": comp.get("qty_adjustment"),
            "rate_source": comp.get("rate_source"),
            "status": comp.get("status"),
            "note": comp.get("note"),
        })

    return (
        "Analyze this invoice. The deterministic system has already run. "
        "Your job is to add depth, not override.\n\n"
        f"```json\n{json.dumps(context, indent=2, default=str)}\n```"
    )


def _validate_and_sanitize(raw_response: dict, algorithmic_status: str) -> dict:
    """
    GUARDRAIL ENFORCEMENT — this is where we ensure the LLM can't go rogue.

    Rules:
    1. If algorithmic status is FLAGGED, risk_level cannot be "low"
    2. Risk level must be a valid enum value
    3. Strings are truncated to prevent prompt injection in reports
    4. Lists are capped to prevent flooding
    5. Any invalid field gets a safe default
    """
    sanitized = {}

    # Risk level — constrained to valid values, can't downplay flags
    risk = str(raw_response.get("risk_level", "medium")).lower().strip()
    if risk not in VALID_RISK_LEVELS:
        risk = "medium"
    if algorithmic_status == "FLAGGED" and risk == "low":
        risk = "medium"  # LLM can't say "low risk" when algorithm flagged it
    sanitized["risk_level"] = risk

    # Executive summary — truncated
    summary = str(raw_response.get("executive_summary", ""))[:MAX_EXPLANATION_LEN]
    sanitized["executive_summary"] = summary if summary else "No summary generated."

    # Insights — capped and truncated
    insights = raw_response.get("insights", [])
    if not isinstance(insights, list):
        insights = []
    sanitized["insights"] = [
        str(i)[:300] for i in insights[:MAX_INSIGHTS] if isinstance(i, str) and i.strip()
    ]

    # Questions — capped
    questions = raw_response.get("recommended_questions", [])
    if not isinstance(questions, list):
        questions = []
    sanitized["recommended_questions"] = [
        str(q)[:300] for q in questions[:MAX_QUESTIONS] if isinstance(q, str) and q.strip()
    ]

    # Explanation — truncated
    explanation = str(raw_response.get("explanation", ""))[:MAX_EXPLANATION_LEN]
    sanitized["explanation"] = explanation if explanation else "No explanation generated."

    return sanitized


def analyze_invoice(invoice_data: dict, vendor_match: dict,
                    line_comparisons: list[dict], math_issues: list[str],
                    tax_check: dict, shipping_check: dict,
                    decision_result: dict, db_stats: dict) -> dict:
    """
    Run LLM analysis on a processed invoice.

    Returns a structured analysis dict. If the LLM is unavailable or fails,
    returns a graceful fallback — the system NEVER breaks because of the LLM.
    """
    algorithmic_status = decision_result.get("status", "FLAGGED")

    # Fallback result — used if LLM is unavailable or fails
    fallback = {
        "risk_level": "medium" if algorithmic_status == "FLAGGED" else "low",
        "executive_summary": f"Invoice {invoice_data.get('invoice_number', 'UNKNOWN')} "
                             f"was {algorithmic_status} by the deterministic system.",
        "insights": [],
        "recommended_questions": [],
        "explanation": "LLM analysis unavailable — deterministic results only.",
        "ai_available": False,
        "model": None,
        "latency_ms": 0,
    }

    client = _get_client()
    if client is None:
        reason = "openai package not installed" if not OPENAI_AVAILABLE else "OPENAI_API_KEY not set"
        fallback["explanation"] = f"LLM analysis skipped ({reason}). Deterministic results only."
        return fallback

    # Build prompts
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(
        invoice_data, vendor_match, line_comparisons,
        math_issues, tax_check, shipping_check,
        decision_result, db_stats,
    )

    # Call the LLM with timeout and retry
    start_time = time.time()
    raw_text = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                timeout=TIMEOUT_SECONDS,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(1)
                continue
            fallback["explanation"] = f"LLM call failed after {MAX_RETRIES + 1} attempts: {type(e).__name__}"
            return fallback

    latency_ms = int((time.time() - start_time) * 1000)

    # Parse JSON response
    try:
        raw_response = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        fallback["explanation"] = "LLM returned invalid JSON. Deterministic results only."
        fallback["latency_ms"] = latency_ms
        return fallback

    # GUARDRAIL: validate and sanitize
    sanitized = _validate_and_sanitize(raw_response, algorithmic_status)
    sanitized["ai_available"] = True
    sanitized["model"] = MODEL
    sanitized["latency_ms"] = latency_ms

    return sanitized


def get_analyzer_status() -> dict:
    """Check if the LLM analyzer is available and configured."""
    has_package = OPENAI_AVAILABLE
    has_key = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    return {
        "available": has_package and has_key,
        "openai_package": has_package,
        "api_key_set": has_key,
        "model": MODEL,
        "guardrails": [
            "LLM cannot override algorithmic flags",
            "LLM cannot approve FLAGGED invoices",
            "LLM risk_level cannot be 'low' when algorithm flags",
            "All outputs are validated, truncated, and sanitized",
            f"Timeout: {TIMEOUT_SECONDS}s — system works without LLM",
            "Structured JSON output only — free text ignored",
        ],
    }
