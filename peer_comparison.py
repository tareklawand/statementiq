"""Conservative user-selected peer comparisons, with visible exclusions."""
import math
from datetime import date, datetime, timezone
from statistics import median

# Values come only from the existing server-side financial calculations.
FIELDS = (
    ("gross_margin", "Gross margin", "ratios", "percent", False, False),
    ("net_margin", "Net margin", "ratios", "percent", False, False),
    ("roe", "Return on equity", "ratios", "percent", False, False),
    ("roa", "Return on assets", "ratios", "percent", False, False),
    ("debt_to_equity", "Debt / equity", "ratios", "multiple", False, False),
    ("operating_margin", "Operating margin", "supplemental_metrics", "percent", False, False),
    ("free_cash_flow_margin", "Free cash flow margin", "supplemental_metrics", "percent", False, False),
    ("pe_ratio", "P/E", "ratios", "multiple", True, True),
    ("ev_ebitda", "EV / EBITDA", "ratios", "multiple", True, True),
    ("price_to_book", "Price / book", "advanced_metrics", "multiple", True, True),
    ("free_cash_flow_yield", "Free cash flow yield", "supplemental_metrics", "percent", True, False),
)


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _quote_time(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result if result.tzinfo else None
    except ValueError:
        return None


def compare_peers(payloads, universe="industry", now=None):
    """First issuer anchors the cohort. Invalid evidence never becomes zero."""
    if universe not in {"industry", "sector"}:
        raise ValueError("Choose industry or sector peers")
    now = now or datetime.now(timezone.utc)
    anchor = payloads[0]
    profile = anchor.get("metrics", {}).get("applicability_profile", {}).get("key")
    anchor_info = anchor.get("info") or {}
    anchor_basis = (anchor.get("data_quality") or {}).get("analysis_basis") or {}
    flow_end = _date(anchor_basis.get("income_period_end"))
    balance_end = _date(anchor_basis.get("balance_sheet_period_end"))
    cash_end = _date(anchor_basis.get("cash_flow_period_end"))
    anchor_quote = _quote_time((anchor.get("data_quality") or {}).get("market_data_as_of"))
    selected = []
    for index, payload in enumerate(payloads):
        info, quality, metrics = (payload.get(key) or {} for key in ("info", "data_quality", "metrics"))
        basis = quality.get("analysis_basis") or {}
        reasons = []
        if payload.get("error"):
            reasons.append(payload["error"])
        if not profile or profile == "classification_unavailable" or (metrics.get("applicability_profile") or {}).get("key") != profile:
            reasons.append("Company-model classifications do not match or are unverified")
        if not anchor_info.get("currency") or info.get("currency") != anchor_info["currency"]:
            reasons.append("Statement currencies do not match or are unavailable")
        if not anchor_info.get(universe) or str(info.get(universe) or "").casefold() != str(anchor_info[universe]).casefold():
            reasons.append(f"The selected {universe} classifications do not match or are unavailable")
        if profile in {"financial_institution", "reit"} and (not info.get("industry") or not anchor_info.get("industry") or
                str(info["industry"]).casefold() != str(anchor_info["industry"]).casefold()):
            reasons.append("Financial institutions and REITs require matching industry classifications even in a broader-sector group")
        if quality.get("integrity_hold_reason"):
            reasons.append("Financial-integrity or freshness hold")
        for key, anchor_end in (("income", flow_end), ("balance_sheet", balance_end)):
            peer_end = _date(basis.get(key + "_period_end"))
            if not anchor_end or not peer_end or abs((peer_end - anchor_end).days) > 45 or max(anchor_end, peer_end) > now.date():
                reasons.append(f"{key.replace('_', ' ').title()} periods are missing or more than 45 days apart")
        # TTM and a complete fiscal year both represent annual flows, but a
        # standalone quarter is never compared as if it represented a year.
        valid_flow_bases = {"latest_annual", "trailing_twelve_months"}
        if basis.get("income") not in valid_flow_bases or anchor_basis.get("income") not in valid_flow_bases:
            reasons.append("Annual/TTM reporting bases are unavailable")
        quote = _quote_time(quality.get("market_data_as_of"))
        quote_ok = bool(anchor_quote and quote and abs((quote - anchor_quote).total_seconds()) <= 36 * 3600 and
                        0 <= (now - quote).total_seconds() <= 7 * 86400 and
                        0 <= (now - anchor_quote).total_seconds() <= 7 * 86400)
        values, unavailable = {}, {}
        for key, label, group, unit, market, positive in FIELDS:
            value = (metrics.get(group) or {}).get(key)
            reason = None
            if reasons:
                reason = "; ".join(dict.fromkeys(reasons))
            elif key in {"free_cash_flow_margin", "free_cash_flow_yield"} and (
                not cash_end or not _date(basis.get("cash_flow_period_end")) or
                abs((_date(basis["cash_flow_period_end"]) - cash_end).days) > 45 or
                abs((_date(basis["cash_flow_period_end"]) - _date(basis["income_period_end"])).days) > 14 or
                abs((cash_end - flow_end).days) > 14 or
                basis.get("cash_flow") not in valid_flow_bases or anchor_basis.get("cash_flow") not in valid_flow_bases):
                reason = "Cash-flow periods or annual/TTM bases do not align"
            elif market and not quote_ok:
                reason = "Quote timestamps are missing, older than seven days, or more than 36 hours apart"
            elif not _number(value):
                reason = "Source value is unavailable or not applicable"
            elif positive and value <= 0:
                reason = "A positive denominator/multiple is required for this valuation comparison"
            values[key] = float(value) if reason is None else None
            if reason:
                unavailable[key] = reason
        selected.append({"symbol": payload["symbol"], "company_name": payload.get("company_name"), "anchor": index == 0,
            "included": not reasons, "exclusions": list(dict.fromkeys(reasons)), "values": values, "unavailable": unavailable,
            "currency": info.get("currency"), "sector": info.get("sector"), "industry": info.get("industry"),
            "company_model": (metrics.get("applicability_profile") or {}).get("key"),
            "reporting_basis": basis, "quote_as_of": quality.get("market_data_as_of"),
            "statement_source": quality.get("statement_provider"), "market_source": quality.get("market_provider"),
            "input_sha256": payload.get("input_sha256"), "methodology": payload.get("methodology")})
    summaries = []
    for key, label, group, unit, market, positive in FIELDS:
        values = [row["values"][key] for row in selected if not row["anchor"] and row["values"][key] is not None]
        summaries.append({"key": key, "label": label, "unit": unit, "peer_count": len(values),
                          "peer_median": median(values) if len(values) >= 2 else None,
                          "median_scope": "Excludes the selected company; requires at least two comparable peers."})
    return {"anchor": anchor["symbol"], "universe": universe, "companies": selected, "measures": summaries,
            "scope": "User-selected peers only. Filters check company model, reporting currency, annual/TTM bases, period alignment and dated quotes. They do not establish equivalent accounting policies or economic businesses. Missing figures are excluded, not zero. This is not a valuation recommendation."}
