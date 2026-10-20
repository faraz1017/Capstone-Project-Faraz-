"""
narrator/generate_narrative.py — Part 3: GenAI-powered insight narrator.

Turns the verified figures in narrator/findings.json into a business
narrative with three sections: Situation, Complication, Resolution (SCR).

Two paths, same output shape:
  * Online  - Google Gemini (free AI Studio key), used when GEMINI_API_KEY is set.
  * Offline - a fixed template, used when there is no key or the API call fails.
    Needs no key, no network and no setup.

Run from the repo root, after analysis/clean_and_eda.py:
    python narrator/generate_narrative.py
"""

import json
import os
import sys
from pathlib import Path

# Gemini may reply with characters such as the rupee sign, which the default
# Windows console cannot print. This prevents a crash on such characters.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NARRATOR_DIR = Path(__file__).resolve().parent
FINDINGS_PATH = NARRATOR_DIR / "findings.json"
SAMPLE_OUTPUT_PATH = NARRATOR_DIR / "sample_output.txt"

# Free-tier model; can be changed without editing code: set GEMINI_MODEL.
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

# Fixes the model's role, structure and rules. Sent separately from the
# data (as a system instruction), so the rules cannot be confused with it.
SYSTEM_INSTRUCTION = """You are a senior data analyst writing for Mamaearth's regional ops and finance heads.

Write a business narrative of about 250 words in exactly three labeled sections,
in this order, each starting with its label on its own line:
Situation:
Complication:
Resolution:

Rules:
- Every number you write must come from the findings supplied by the user and must
  appear with exactly the same value. Do not invent, estimate or round any statistic.
- Write money in Indian Rupees as INR with two decimals and thousands separators
  (for example INR 1,234.50). Write percentages with one decimal (for example 12.3%).
- Refer to months by name (for example March 2026), not as 2026-03.
- Plain business English for non-technical readers. No markdown, bullet symbols or tables.
"""


def load_findings(path=FINDINGS_PATH):
    """Read the verified figures written by analysis/clean_and_eda.py."""
    if not path.exists():
        sys.exit("narrator/findings.json not found - run `python analysis/clean_and_eda.py` first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def month_name(year_month):
    """'2026-03' -> 'March 2026'."""
    year, month = year_month.split("-")
    names = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
    return f"{names[int(month) - 1]} {year}"


def build_user_prompt(findings):
    """Build the prompt from the findings dict. No number is typed here:
    a different findings.json produces a different prompt automatically."""
    rates = findings["return_rate_by_payment"]
    rate_lines = "\n".join(f"  - {method}: {rate:.1f}%" for method, rate in rates.items())
    risk = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]

    return f"""Write the SCR narrative using only these verified findings.

Revenue:
  - Raw total revenue (before cleaning): INR {findings['raw_total_revenue_inr']:,.2f}
  - Cleaned total revenue: INR {findings['cleaned_total_revenue_inr']:,.2f}
  - Difference, caused entirely by duplicate (double-submitted) orders: INR {findings['duplicate_reconciliation_delta_inr']:,.2f}

Return rate by payment method:
{rate_lines}

Highest-risk segment: {risk['payment_method']} orders in Tier-{risk['city_tier']} cities, return rate {risk['return_rate_pct']:.1f}%

Monthly revenue:
  - {month_name(inflated['month'])} looked like the best month at INR {inflated['apparent_revenue_inr']:,.2f},
    but only because of bulk outlier orders; without them it is INR {inflated['corrected_revenue_inr']:,.2f}.
  - The true peak month is {month_name(peak['month'])} at INR {peak['revenue_inr']:,.2f}.

The Resolution should recommend concrete actions for the highest-risk segment."""


def generate_scr_narrative(findings: dict) -> dict:
    """Online path: ask Gemini for the SCR narrative.

    Always returns a dict, never raises:
      success -> {"status": "success", "narrative": str, "tokens": int, ...}
      failure -> {"status": "error", "narrative": None, "message": str}
    """
    try:
        # Imported here so the offline path still works if the library is missing.
        from google import genai
        from google.genai import types

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        client = genai.Client(
            api_key=api_key,
            # Timeout is in MILLISECONDS: 30000 = 30 seconds (not 30).
            http_options=types.HttpOptions(timeout=30000),
        )

        # Gemini 2.5 models can spend output tokens on hidden "thinking"; this
        # setting turns it off for them. Newer models manage thinking
        # differently and may reject it, so it is only sent for 2.5 models.
        thinking = types.ThinkingConfig(thinking_budget=0) if "2.5" in MODEL_NAME else None

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            # temperature 0 = most deterministic wording. This is a factual
            # business report, not creative writing: we want the same figures
            # stated plainly every time, not variety.
            temperature=0.0,
            # Explicit cap on reply length. A ~250-word narrative needs about
            # 350 tokens; 2048 leaves room for any hidden thinking tokens so
            # the narrative is never cut off mid-sentence.
            max_output_tokens=2048,
            thinking_config=thinking,
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=build_user_prompt(findings),
            config=config,
        )

        if not response.text:
            raise RuntimeError("Gemini returned an empty response")

        usage = response.usage_metadata
        return {
            "status": "success",
            "narrative": response.text.strip(),
            "tokens": usage.total_token_count if usage else None,
            "finish_reason": str(response.candidates[0].finish_reason),
            "source": f"gemini ({MODEL_NAME})",
        }
    except Exception as err:  # any failure becomes a dict, never a crash
        return {"status": "error", "narrative": None, "message": str(err)}


def generate_scr_narrative_offline(findings: dict) -> dict:
    """Offline path: the same three SCR sections from a fixed template.
    No network and no API key; every figure comes from findings."""
    rates = findings["return_rate_by_payment"]
    risk = findings["highest_risk_segment"]
    peak = findings["true_peak_month"]
    inflated = findings["outlier_inflated_month"]
    cod_rate = rates[risk["payment_method"]]
    other_rates = ", ".join(
        f"{method} {rate:.1f}%" for method, rate in rates.items() if method != risk["payment_method"]
    )

    narrative = f"""Situation:
Across January to June 2026, Mamaearth's cleaned order data shows total revenue of INR {findings['cleaned_total_revenue_inr']:,.2f}. The raw order table reported INR {findings['raw_total_revenue_inr']:,.2f}, but INR {findings['duplicate_reconciliation_delta_inr']:,.2f} of that came from double-submitted duplicate orders, which have been removed. Monthly revenue looked strongest in {month_name(inflated['month'])} at INR {inflated['apparent_revenue_inr']:,.2f}, but that figure was inflated by bulk outlier orders; without them it is INR {inflated['corrected_revenue_inr']:,.2f}, and the true peak month is {month_name(peak['month'])} at INR {peak['revenue_inr']:,.2f}.

Complication:
Returns are concentrated in cash-on-delivery orders. {risk['payment_method']} orders are returned at {cod_rate:.1f}%, compared with {other_rates}. The blended rate hides a sharper problem: {risk['payment_method']} orders from Tier-{risk['city_tier']} cities are returned at {risk['return_rate_pct']:.1f}%, the highest of any payment-method and city-tier segment.

Resolution:
Target the {risk['payment_method']} plus Tier-{risk['city_tier']} segment first rather than applying a blanket policy: confirm these orders by call or message before dispatch, and offer a small incentive to switch to prepaid payment. Track the {risk['return_rate_pct']:.1f}% segment return rate monthly to measure the effect. Finance should report revenue on the cleaned basis and fix the duplicate-submission bug, and planning should treat {month_name(peak['month'])}, not {month_name(inflated['month'])}, as the demand benchmark."""

    return {
        "status": "success",
        "narrative": narrative,
        "tokens": 0,  # no model was called
        "source": "offline template",
    }


def generate_narrative(findings: dict) -> dict:
    """Try Gemini first; fall back to the offline template if there is no
    key or the call fails, so the pipeline always produces a narrative."""
    if os.environ.get("GEMINI_API_KEY"):
        result = generate_scr_narrative(findings)
        if result["status"] == "success":
            return result
        print(f"Gemini call failed ({result['message']}); using offline fallback.\n")
    else:
        print("No GEMINI_API_KEY set; using offline fallback.\n")
    return generate_scr_narrative_offline(findings)


def check_numeric_accuracy(narrative: str, findings: dict) -> bool:
    """Confirm the five key figures appear in the narrative.

    Commas are removed first, so '97,358.30' and '97358.3' both match.
    Expected values are read from findings, not typed in.
    """
    text = narrative.replace(",", "")
    peak = findings["true_peak_month"]
    peak_month_word = month_name(peak["month"]).split()[0]  # e.g. 'March'

    def money(value):
        # 97358.3 -> '97358.3', which is also found inside '97358.30'
        return f"{value:.2f}".rstrip("0").rstrip(".")

    checks = [
        ("Cleaned total revenue", money(findings["cleaned_total_revenue_inr"])),
        ("COD return rate", f"{findings['return_rate_by_payment']['COD']:.1f}"),
        ("Highest-risk segment rate", f"{findings['highest_risk_segment']['return_rate_pct']:.1f}"),
        ("Duplicate reconciliation delta", money(findings["duplicate_reconciliation_delta_inr"])),
    ]

    all_passed = True
    for label, expected in checks:
        found = expected in text
        all_passed = all_passed and found
        print(f"  [{'PASS' if found else 'FAIL'}] {label}: {expected}")

    peak_value = money(peak["revenue_inr"])
    found = peak_month_word in text and peak_value in text
    all_passed = all_passed and found
    print(f"  [{'PASS' if found else 'FAIL'}] True peak month: {peak_month_word} + {peak_value}")

    print(f"  Overall: {'PASS - all 5 figures present' if all_passed else 'FAIL'}")
    return all_passed


if __name__ == "__main__":
    findings = load_findings()

    result = generate_narrative(findings)
    print(f"Narrative source: {result['source']} | tokens: {result['tokens']}")
    if result.get("finish_reason") and "STOP" not in result["finish_reason"]:
        print(f"Warning: Gemini stopped early ({result['finish_reason']}); output may be cut off.")
    print("-" * 70)
    print(result["narrative"])
    print("-" * 70)

    print("\nNumeric accuracy check (this run):")
    check_numeric_accuracy(result["narrative"], findings)

    # A successful Gemini run is saved as the graded sample. Offline runs never
    # overwrite it, so a grader without a key still sees the real Gemini output.
    if result["source"].startswith("gemini"):
        SAMPLE_OUTPUT_PATH.write_text(result["narrative"] + "\n", encoding="utf-8")
        print(f"\nSaved Gemini output to {SAMPLE_OUTPUT_PATH.name}")

    if SAMPLE_OUTPUT_PATH.exists():
        print(f"\nNumeric accuracy check (saved Gemini sample, {SAMPLE_OUTPUT_PATH.name}):")
        check_numeric_accuracy(SAMPLE_OUTPUT_PATH.read_text(encoding="utf-8"), findings)
    else:
        print(f"\nNo {SAMPLE_OUTPUT_PATH.name} yet - run once with GEMINI_API_KEY set to create it.")
