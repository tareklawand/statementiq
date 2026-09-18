import os
import json
from typing import Dict, Any, Optional

COMPANY_SPECIFIC_INTELLIGENCE = {
    "AAPL": {
        "executive_summary": "Apple Inc. (AAPL) demonstrates solid net sales performance in its FY2025 Form 10-K audited filings, supported by $416.161B in annual net sales and $112.010B in net income. Apple’s Services category generated $109.158 billion in FY2025 net sales with a Services gross margin of 75.4%. Apple repurchased $90.711B of common stock during FY2025.",
        "top_strengths": [
            "Return on Equity (ROE using average equity) of 171.4% ($112.010B Net Income / $65.342B Average Equity) affected by share repurchases.",
            "Net Profit Margin of 26.9% ($112.010B Net Income / $416.161B Net Sales) and consolidated gross margin dollars of $195.201B (46.9%).",
            "Return on Assets (ROA using average assets) of 30.9% ($112.010B Net Income / $362.111B Average Total Assets)."
        ],
        "top_weaknesses": [
            "Current Ratio of 0.89 and Strict Quick Ratio of 0.77 ($127.65B Strict Quick Assets / $165.63B Current Liabilities) with negative working capital of -$17.67B.",
            "Debt-to-Equity ratio of 1.34 ($98.66B Total Disclosed Borrowings / $73.73B Shareholders Equity).",
            "TTM P/E valuation multiple of 40.22x and EV/EBITDA of 34.10x (as of July 30, 2026 3:45:16 PM UTC) exceed model valuation benchmarks."
        ],
        "score_explanation": "The Financial Health and Valuation Score of 68/100 is calculated via a 100% deterministic quantitative model weighing 10 ratios (Healthy=1.0, Caution=0.6, Warning=0.2). Apple scores Healthy on Net Margin (26.9%), ROE (171.4%), ROA (30.9%), Asset Turnover (1.15x), Gross Margin (46.9%), and Debt-to-Equity (1.34), and Warning on Current Ratio (0.89), Strict Quick Ratio (0.77), TTM P/E (40.22x), and EV/EBITDA (34.10x)."
    }
}

def generate_ai_insights(company_name: str, symbol: str, health_score: Optional[int], ratios_summary: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    # Deliberately use the deterministic path only. Free-form model output and
    # ticker-specific snapshots can introduce claims that are not present in the
    # current source dataset.
    return generate_custom_ticker_insights(company_name, symbol, health_score, ratios_summary)

    # Legacy implementation retained below for compatibility history only.
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if effective_api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=effective_api_key)

            prompt = f"""
You are a senior Wall Street equity research analyst. Analyze the financial metrics and ratios for {company_name} ({symbol}):

Financial Health Score: {health_score}/100

Key Financial Ratios & Benchmark Status:
{json.dumps(ratios_summary, indent=2)}

Generate a neutral factual assessment in STRICT JSON format with the following exact keys:
1. "executive_summary": A concise 3-4 sentence narrative summarizing audited financial statements.
2. "top_strengths": An array of EXACTLY 3 key financial strengths mentioning specific ratio values.
3. "top_weaknesses": An array of EXACTLY 3 key financial risks mentioning specific metric context.
4. "score_explanation": A detailed explanation of why the company achieved a score of {health_score}/100.

Return ONLY raw JSON.
"""

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            if response and response.text:
                clean_text = response.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
                elif clean_text.startswith("```"):
                    clean_text = clean_text.split("```", 1)[1].rsplit("```", 1)[0].strip()
                
                return json.loads(clean_text)

        except Exception:
            pass

    if symbol in COMPANY_SPECIFIC_INTELLIGENCE:
        res = COMPANY_SPECIFIC_INTELLIGENCE[symbol].copy()
        res["score_explanation"] = f"The Financial Health and Valuation Score of {health_score}/100 is calculated via a 100% deterministic quantitative model weighing 10 ratios based on audited SEC FY2025 Form 10-K filings and intraday market quotes."
        return res

    return generate_custom_ticker_insights(company_name, symbol, health_score, ratios_summary)

def generate_custom_ticker_insights(company_name: str, symbol: str, health_score: Optional[int], ratios_summary: Dict[str, Any]) -> Dict[str, Any]:
    strengths = []
    weaknesses = []

    for key, eval_data in ratios_summary.items():
        name = eval_data.get("name", key)
        val = eval_data.get("value")
        fmt = eval_data.get("format", "{:.2f}")
        status = eval_data.get("status")
        target = eval_data.get("target", "")

        if status == "Healthy":
            try:
                val_str = fmt.format(val) if val is not None else "N/A"
            except Exception:
                val_str = str(val)
            strengths.append(f"{name} of {val_str} demonstrating strong alignment with model benchmark targets ({target}).")
        elif status in ["Caution", "Warning"]:
            try:
                val_str = fmt.format(val) if val is not None else "N/A"
            except Exception:
                val_str = str(val)
            weaknesses.append(f"{name} of {val_str} reflecting potential room for balance sheet or valuation optimization relative to target ({target}).")
        elif status == "N/M":
            weaknesses.append(f"{name} marked Not Meaningful (N/M) — {target}.")
        elif status == "N/A":
            pass

    applicable_count = sum(
        1 for item in ratios_summary.values()
        if item.get("status") in ["Healthy", "Caution", "Warning"]
    )
    if not strengths:
        strengths.append("No available ratio met the model's Healthy benchmark range.")
    if not weaknesses:
        weaknesses.append("No available ratio fell in a Caution, Warning, or Not Meaningful category.")

    if health_score is None:
        summary = f"{company_name} ({symbol}) does not have enough applicable source fields to calculate a model health score. Missing inputs remain N/A and are not estimated."
        explanation = f"{applicable_count} applicable ratios were available. A score is shown only when at least one weighted ratio can be calculated from reported inputs."
    else:
        summary = f"{company_name} ({symbol}) has {applicable_count} applicable calculated ratios and a rules-based model score of {health_score}/100. The score is an analytical classification, not a reported company figure."
        explanation = f"The {health_score}/100 model score is the normalized weighted result for the {applicable_count} applicable ratios. Ratios marked N/A or N/M contribute no points and are excluded from the denominator."

    return {
        "executive_summary": summary,
        "top_strengths": strengths[:3],
        "top_weaknesses": weaknesses[:3],
        "score_explanation": explanation
    }
