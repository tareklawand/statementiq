"""Period-aligned research evidence. Review prompts are not causal findings."""
from __future__ import annotations

import hashlib
import json
import math
import os
from importlib.metadata import version as package_version
from datetime import date
from pathlib import Path

VERSION = "2026.11.04-research-1"
_ROOT = Path(__file__).resolve().parent
_MODEL_FILES = ("main.py", "data_fetcher.py", "metrics_calculator.py", "sec_filing_validator.py",
                "sec_facts_validator.py", "sec_statement_importer.py", "statement_analysis.py",
                "sector_analysis.py", "deterministic_analyst.py", "evidence_snapshot.py", "research_review.py")


def methodology():
    hashes = {name: hashlib.sha256((_ROOT / name).read_bytes()).hexdigest() for name in _MODEL_FILES}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"version": VERSION, "code_sha256": digest, "components": hashes,
            "source_revision": os.environ.get("RENDER_GIT_COMMIT"),
            "calculation_libraries": {name: package_version(name) for name in ("pandas", "numpy")},
            "status": "Research screen; independently unvalidated", "independent_validation": False}


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def input_fingerprint(payload):
    inputs = {"symbol": payload["symbol"], "info": payload.get("info"), "statements": payload.get("statements"),
              "raw_financials": (payload.get("metrics") or {}).get("raw_financials"),
              "analysis_basis": (payload.get("data_quality") or {}).get("analysis_basis"),
              "source_filing": (payload.get("data_quality") or {}).get("sec_filing"),
              "source_provenance": ((payload.get("data_quality") or {}).get("sec_statement_import") or {}).get("provenance")}
    return hashlib.sha256(canonical_json(inputs).encode()).hexdigest()


def _number(value):
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def _date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


DEFINITIONS = {
    "income_statement": (
        ("revenue", "Revenue", ("Total Revenue", "Operating Revenue", "Revenue")),
        ("gross_profit", "Gross profit", ("Gross Profit",)),
        ("operating_income", "Operating income", ("Operating Income",)),
        ("net_income", "Net income", ("Net Income", "Net Income Common Stockholders")),
        ("diluted_eps", "Diluted EPS", ("Diluted EPS",)),
        ("diluted_shares", "Diluted average shares", ("Diluted Average Shares",)),
    ),
    "cash_flow": (
        ("operating_cash_flow", "Operating cash flow", ("Operating Cash Flow", "Total Cash From Operating Activities")),
        ("capital_expenditure", "Capital expenditure", ("Capital Expenditure", "Capital Expenditures")),
        ("free_cash_flow", "Free cash flow", ("Free Cash Flow",)),
        ("stock_compensation", "Stock-based compensation", ("Stock Based Compensation",)),
    ),
    "balance_sheet": (
        ("assets", "Total assets", ("Total Assets",)),
        ("debt", "Total debt", ("Total Debt",)),
        ("equity", "Stockholders' equity", ("Stockholders Equity", "Common Stock Equity")),
        ("cash", "Cash and current investments", ("Cash Cash Equivalents And Short Term Investments",)),
        ("receivables", "Receivables", ("Receivables", "Accounts Receivable")),
    ),
}


def _comparison(payload, name, frequency):
    key = ("quarterly_" if frequency == "quarterly" else "") + name
    statement = (payload.get("statements") or {}).get(key) or {}
    periods = statement.get("columns") or []
    if not periods or not _date(periods[0]):
        return []
    current_date = _date(periods[0])
    prior_indices = [i for i, period in enumerate(periods) if _date(period) and 350 <= (current_date - _date(period)).days <= 380]
    if len(prior_indices) != 1:
        return []
    prior_index = prior_indices[0]
    rows = {str(row.get("metric", "")).lower(): row for row in statement.get("rows") or []}
    result = []
    for metric, label, aliases in DEFINITIONS[name]:
        row = next((rows[alias.lower()] for alias in aliases if alias.lower() in rows), None)
        if not row:
            continue
        values = row.get("values") or []
        if len(values) <= prior_index:
            continue
        current, prior = _number(values[0]), _number(values[prior_index])
        if current is None or prior is None:
            continue
        result.append({"id": f"{frequency}:{name}:{metric}", "metric": metric, "label": label,
                       "statement": name, "frequency": frequency, "comparison": "year_over_year",
                       "current_period": periods[0], "prior_period": periods[prior_index],
                       "current": current, "prior": prior, "absolute_change": current - prior,
                       "percent_change": current / prior - 1 if prior > 0 else None,
                       "unit": "per_share" if metric == "diluted_eps" else "shares" if metric == "diluted_shares" else (payload.get("info") or {}).get("currency"),
                       "source_row": row["metric"], "source": (payload.get("data_quality") or {}).get("statement_provider"),
                       "filing_url": ((payload.get("data_quality") or {}).get("sec_filing") or {}).get("filing_url")})
    return result


def build_research_review(payload):
    changes = [change for frequency in ("annual", "quarterly") for name in DEFINITIONS for change in _comparison(payload, name, frequency)]
    flags = []
    profile = ((payload.get("metrics") or {}).get("applicability_profile") or {}).get("key")
    if profile != "financial_institution":
        for frequency in ("annual", "quarterly"):
            selected = {c["metric"]: c for c in changes if c["frequency"] == frequency}
            net, cash, revenue, receivables = (selected.get(key) for key in ("net_income", "operating_cash_flow", "revenue", "receivables"))
            def aligned(a, b):
                return a and b and all(abs((_date(a[key]) - _date(b[key])).days) <= 14 for key in ("current_period", "prior_period"))
            if aligned(net, cash) and net["absolute_change"] > 0 and cash["absolute_change"] < 0:
                flags.append({"key": "earnings_cash_divergence", "frequency": frequency,
                              "title": "Net income rose while operating cash flow fell",
                              "note": "Review working-capital movements and noncash income. This comparison does not establish the cause.",
                              "evidence": [net["id"], cash["id"]]})
            if aligned(revenue, receivables) and all(c["percent_change"] is not None for c in (revenue, receivables)) and receivables["percent_change"] > revenue["percent_change"]:
                flags.append({"key": "receivables_growth", "frequency": frequency,
                              "title": "Receivables grew faster than revenue",
                              "note": "Review collection timing, customer mix and disclosed revenue policies. This is not a finding of misstatement.",
                              "evidence": [revenue["id"], receivables["id"]]})
    return {"changes": changes, "review_signals": flags,
            "scope": "Annual and quarterly year-over-year comparisons use actual period dates. Annual figures and discrete quarters are never mixed. Review signals do not change the financial-health score.",
            "missing_comparisons": [frequency for frequency in ("annual", "quarterly") if not any(c["frequency"] == frequency for c in changes)]}
