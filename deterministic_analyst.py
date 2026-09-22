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

    for key, item in ratios_summary.items():
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
        1 for item in ratios_summary.values()
        if item.get("status") in {"Healthy", "Caution", "Warning"}
    )
    if not strengths:
        strengths.append("No available ratio was classified in the model's Healthy range.")
    if not weaknesses:
        weaknesses.append("No available ratio was classified Caution, Warning, or Not Meaningful.")

    withheld_reason = (score_coverage or {}).get("withheld_reason")
    if health_score is None and withheld_reason:
        summary = (
            f"{company_name} ({symbol}) has {applicable_count} applicable calculated ratios, but StatementIQ is not "
            f"publishing a headline score. {withheld_reason} The available figures remain visible for review."
        )
        explanation = (
            f"{withheld_reason} A withheld score is not a negative investment opinion; it means the current evidence "
            "does not support a responsible general-model classification."
        )
    elif health_score is None:
        summary = (
            f"{company_name} ({symbol}) has {applicable_count} applicable calculated ratios, "
            "which is not enough coverage to publish a rules-based score. Missing inputs remain "
            "N/A and are not estimated."
        )
        explanation = (
            "The score is withheld when too few model ratios can be calculated. This avoids "
            "presenting a precise-looking result based on partial financial data."
        )
    else:
        summary = (
            f"{company_name} ({symbol}) has {applicable_count} applicable calculated ratios and "
            f"a rules-based model score of {health_score}/100. The score is an analytical screen, "
            "not a reported company figure or investment recommendation."
        )
        explanation = (
            f"The {health_score}/100 score is the normalized weighted result for the "
            f"{applicable_count} applicable ratios. N/A and N/M ratios contribute no points and "
            "are excluded from the denominator."
        )

    return {
        "executive_summary": summary,
        "top_strengths": strengths[:3],
        "top_weaknesses": weaknesses[:3],
        "score_explanation": explanation,
    }
