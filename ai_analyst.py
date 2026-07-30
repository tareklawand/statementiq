import os
import json
from typing import Dict, Any, Optional

def generate_ai_insights(company_name: str, symbol: str, health_score: int, ratios_summary: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates AI analysis using Google Gemini API (`google-genai` SDK).
    Returns structured dict with executive_summary, top_strengths, top_weaknesses, score_explanation.
    Falls back gracefully to heuristic rule-based insights if key is omitted or API call fails.
    """
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if effective_api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=effective_api_key)

            prompt = f"""
You are a senior Wall Street financial analyst. Analyze the following financial metrics and ratios for {company_name} ({symbol}):

Financial Health Score: {health_score}/100

Key Financial Ratios & Benchmark Status:
{json.dumps(ratios_summary, indent=2)}

Generate a comprehensive financial assessment in STRICT JSON format with the following exact keys:
1. "executive_summary": A concise 3-4 sentence narrative summarizing financial standing and growth potential.
2. "top_strengths": An array of EXACTLY 3 key financial strengths with specific metric values.
3. "top_weaknesses": An array of EXACTLY 3 key financial risks or areas for improvement with metric context.
4. "score_explanation": A detailed explanation of why the company achieved a Financial Health Score of {health_score}/100.

Return ONLY raw JSON, with no markdown codeblocks or formatting outside the JSON object.
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
                
                parsed_json = json.loads(clean_text)
                return parsed_json

        except Exception as e:
            # Fall through to heuristic fallback
            pass

    # Heuristic Rule-Based Fallback
    return generate_fallback_insights(company_name, symbol, health_score, ratios_summary)

def generate_fallback_insights(company_name: str, symbol: str, health_score: int, ratios_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Generates structured analytical insights based on deterministic financial rules."""
    healthy_items = []
    warning_items = []
    
    for key, eval_data in ratios_summary.items():
        name = eval_data.get("name", key)
        val = eval_data.get("value")
        fmt = eval_data.get("format", "{:.2f}")
        status = eval_data.get("status")
        
        if val is not None and status == "Healthy":
            try:
                val_str = fmt.format(val)
            except Exception:
                val_str = str(val)
            healthy_items.append(f"{name} at {val_str} (Target: {eval_data.get('target')})")
        elif val is not None and status in ["Caution", "Warning"]:
            try:
                val_str = fmt.format(val)
            except Exception:
                val_str = str(val)
            warning_items.append(f"{name} at {val_str} (Target: {eval_data.get('target')})")

    # Pick top strengths
    strengths = healthy_items[:3]
    while len(strengths) < 3:
        strengths.append(f"Balanced capital allocation and operational execution across core business units.")

    # Pick top weaknesses
    weaknesses = warning_items[:3]
    while len(weaknesses) < 3:
        weaknesses.append(f"Exposure to broader macroeconomic headwinds and competitive market valuation dynamics.")

    if health_score >= 80:
        summary = f"{company_name} ({symbol}) demonstrates stellar financial resilience characterized by robust operational margins, strong liquidity coverage, and prudent debt management. The company maintains a leading competitive position with solid returns on capital."
        explanation = f"The Financial Health Score of {health_score}/100 reflects top-tier balance sheet strength, sustained profitability metrics, and healthy cash flow generation exceeding market benchmarks."
    elif health_score >= 60:
        summary = f"{company_name} ({symbol}) exhibits moderate financial stability. While profitability and debt management remain stable, certain efficiency or liquidity indicators suggest room for operational optimization."
        explanation = f"The score of {health_score}/100 highlights a solid core business model balanced by neutral liquidity buffers or elevated valuation multiples relative to historical averages."
    else:
        summary = f"{company_name} ({symbol}) presents an elevated risk profile with compressed operating margins and stretched leverage or liquidity ratios relative to industry standard benchmarks."
        explanation = f"The score of {health_score}/100 is constrained by sub-optimal debt coverage, margin pressure, or lagging asset turnover efficiency."

    return {
        "executive_summary": summary,
        "top_strengths": strengths,
        "top_weaknesses": weaknesses,
        "score_explanation": explanation
    }
