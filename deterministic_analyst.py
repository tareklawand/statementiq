"""Deterministic narrative generation from calculated results only.

No ticker-specific claims, model completions, or stale snapshots are used here.
Every number in the briefing comes from the current calculation response.
"""

from typing import Any, Dict, Optional


def generate_ai_insights(
    company_name: str,
    symbol: str,
    health_score: Optional[int],
    ratios_summary: Dict[str, Any],
    api_key: Optional[str] = None,
    score_coverage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    del api_key  # Kept for API compatibility; external model output is disabled.
    return generate_custom_ticker_insights(company_name, symbol, health_score, ratios_summary, score_coverage)


def _format_value(item: Dict[str, Any]) -> str:
    value = item.get("value")
    if value is None:
        return "N/A"
    try:
        return item.get("format", "{:.2f}").format(value)
    except (TypeError, ValueError):
        return str(value)


def generate_custom_ticker_insights(
    company_name: str,
    symbol: str,
    health_score: Optional[int],
    ratios_summary: Dict[str, Any],
    score_coverage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    strengths = []
    weaknesses = []
    health_items = {
        key: item for key, item in ratios_summary.items()
        if item.get("score_model", "financial_health") == "financial_health"
    }

    for key, item in health_items.items():
        name = item.get("name", key)
        status = item.get("status")
        value_text = _format_value(item)
        target = item.get("target", "")
        if status == "Healthy":
            strengths.append(f"{name} is {value_text}, within the model's Healthy range ({target}).")
        elif status in {"Caution", "Warning"}:
            weaknesses.append(f"{name} is {value_text}, classified {status} under the stated model range ({target}).")
        elif status == "N/M":
            weaknesses.append(f"{name} is not meaningful for this calculation: {target}.")

    applicable_count = sum(
        1 for item in health_items.values()
        if item.get("status") in {"Healthy", "Caution", "Warning"}
    )
    if not strengths:
        strengths.append("No available ratio was classified in the model's Healthy range.")
    if not weaknesses:
        weaknesses.append("No available ratio was classified Caution, Warning, or Not Meaningful.")

    withheld_reason = (score_coverage or {}).get("withheld_reason")
    coverage_label = (score_coverage or {}).get("coverage_label", "Low")
    coverage_percent = round(float((score_coverage or {}).get("coverage_percent") or 0) * 100)
    valuation_score = (score_coverage or {}).get("valuation_score")
    valuation_status = (score_coverage or {}).get("valuation_status") or "Insufficient Data"
    score_range = (score_coverage or {}).get("score_range") or {}
    range_sentence = (
        f" The disclosed evidence range is {int(score_range['low'])}–{int(score_range['high'])}/100, "
        "treating unavailable evidence as adverse at the low end and favorable at the high end."
        if score_range.get("low") is not None and score_range.get("high") is not None else ""
    )
    valuation_sentence = (
        f" The separate valuation screen is {int(valuation_score)}/100 ({valuation_status})."
        if valuation_score is not None else
        f" The separate valuation screen is withheld ({valuation_status})."
    )
    if health_score is None and withheld_reason:
        summary = (
            f"{company_name} ({symbol}) has {applicable_count} applicable financial-health inputs, but StatementIQ is not "
            f"publishing a headline score for financial health. {withheld_reason} The available figures remain visible for review.{valuation_sentence}"
        )
        explanation = (
            f"{withheld_reason} A withheld score is not a negative investment opinion; it means the current evidence "
            "does not support a responsible general-model classification."
        )
    elif health_score is None:
        summary = (
            f"{company_name} ({symbol}) has {applicable_count} applicable financial-health inputs and "
            f"{coverage_label.lower()} model coverage ({coverage_percent}%), which is not enough to publish a health score. "
            f"Missing inputs remain N/A and are not estimated.{valuation_sentence}"
        )
        explanation = (
            "The score is withheld when too few model ratios can be calculated. This avoids "
            "presenting a precise-looking result based on partial financial data."
        )
    else:
        summary = (
            f"{company_name} ({symbol}) has a financial-health score of {health_score}/100 from "
            f"{applicable_count} applicable inputs with {coverage_label.lower()} model coverage ({coverage_percent}%)."
            f"{range_sentence}{valuation_sentence} These are analytical screens, not reported company figures or investment recommendations."
        )
        explanation = (
            f"The {health_score}/100 health score combines five capped components: liquidity, solvency, "
            "profitability and efficiency, cash-flow quality, and growth with per-share resilience. "
            "Only metrics labelled Health score input contribute. Valuation and context-only metrics are excluded; "
            "N/A and N/M values receive no points and reduce disclosed coverage. A score is published only with at least "
            "80% of intended model weight and evidence in all five components."
        )

    return {
        "executive_summary": summary,
        "top_strengths": strengths[:3],
        "top_weaknesses": weaknesses[:3],
        "score_explanation": explanation,
    }
