"""Cross-check selected provider statement rows against SEC Company Facts."""

from __future__ import annotations

import math
import os
import time
from datetime import date
from typing import Any, Dict, Iterable, Optional

import pandas as pd
import requests


_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_TTL = 15 * 60
_PERIODIC_FORMS = {"10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}


def _headers() -> Dict[str, str]:
    return {
        "User-Agent": os.environ.get(
            "SEC_USER_AGENT",
            "StatementIQ/1.0 (statementiq-lb.com; financial-data validation)",
        ),
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate",
    }


def _row_value(df: pd.DataFrame, aliases: Iterable[str]) -> Optional[float]:
    if df is None or df.empty:
        return None
    index = {str(name).strip().lower(): name for name in df.index}
    for alias in aliases:
        matched = index.get(alias.strip().lower())
        if matched is None:
            continue
        value = df.loc[matched].iloc[0]
        if pd.notna(value):
            try:
                number = float(value)
                return number if math.isfinite(number) else None
            except (TypeError, ValueError):
                return None
    return None


def _parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    try:
        return pd.Timestamp(value).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _fact_value(
    facts: Dict[str, Any],
    tags: Iterable[str],
    currency: str,
    target_end: date,
    instantaneous: bool,
) -> Optional[Dict[str, Any]]:
    candidates = []
    for taxonomy in ("us-gaap", "ifrs-full"):
        taxonomy_facts = facts.get(taxonomy) or {}
        for tag in tags:
            concept = taxonomy_facts.get(tag) or {}
            unit_values = (concept.get("units") or {}).get(currency) or []
            for item in unit_values:
                if item.get("form") not in _PERIODIC_FORMS:
                    continue
                end = _parse_date(item.get("end"))
                if end is None or abs((end - target_end).days) > 14:
                    continue
                start = _parse_date(item.get("start"))
                if instantaneous and start is not None:
                    continue
                if not instantaneous:
                    if start is None:
                        continue
                    duration_days = (end - start).days
                    if duration_days < 60 or duration_days > 120:
                        continue
                value = item.get("val")
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue
                candidates.append({
                    "value": value,
                    "tag": tag,
                    "taxonomy": taxonomy,
                    "end": item.get("end"),
                    "filed": item.get("filed"),
                    "form": item.get("form"),
                    "accession_number": item.get("accn"),
                })
    if not candidates:
        return None
    return max(candidates, key=lambda item: (str(item.get("filed") or ""), str(item.get("end") or "")))


def validate_core_sec_facts(
    cik: Optional[str],
    quarterly_income: pd.DataFrame,
    quarterly_balance: pd.DataFrame,
    statement_currency: Optional[str],
) -> Dict[str, Any]:
    """Compare latest-quarter core rows with official structured filing facts."""
    if not cik:
        return {"status": "not_applicable", "checked": 0, "matched": 0, "mismatches": []}
    if quarterly_income is None or quarterly_income.empty or quarterly_balance is None or quarterly_balance.empty:
        return {"status": "unavailable", "checked": 0, "matched": 0, "mismatches": [], "reason": "Quarterly provider statements were unavailable."}

    income_end = _parse_date(quarterly_income.columns[0])
    balance_end = _parse_date(quarterly_balance.columns[0])
    if income_end is None or balance_end is None:
        return {"status": "unavailable", "checked": 0, "matched": 0, "mismatches": [], "reason": "Provider period dates were invalid."}

    currency = str(statement_currency or "USD").upper()
    cache_key = f"{str(cik).zfill(10)}:{income_end.isoformat()}:{balance_end.isoformat()}:{currency}"
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached["timestamp"] < _CACHE_TTL:
        return cached["data"]

    definitions = [
        ("revenue", quarterly_income, ["Total Revenue", "Operating Revenue", "Revenue"], ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"], False, income_end),
        ("gross_profit", quarterly_income, ["Gross Profit"], ["GrossProfit"], False, income_end),
        ("operating_income", quarterly_income, ["Operating Income"], ["OperatingIncomeLoss"], False, income_end),
        ("net_income", quarterly_income, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"], ["NetIncomeLoss", "ProfitLoss"], False, income_end),
        ("total_assets", quarterly_balance, ["Total Assets"], ["Assets"], True, balance_end),
        ("current_assets", quarterly_balance, ["Current Assets", "Total Current Assets"], ["AssetsCurrent"], True, balance_end),
        ("current_liabilities", quarterly_balance, ["Current Liabilities", "Total Current Liabilities"], ["LiabilitiesCurrent"], True, balance_end),
        ("stockholders_equity", quarterly_balance, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"], ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"], True, balance_end),
        ("cash_and_equivalents", quarterly_balance, ["Cash And Cash Equivalents", "Cash Financial"], ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"], True, balance_end),
    ]

    try:
        response = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json",
            headers=_headers(),
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json()
        facts = payload.get("facts") or {}

        checks = []
        mismatches = []
        for name, provider_df, aliases, tags, instantaneous, target_end in definitions:
            provider_value = _row_value(provider_df, aliases)
            sec_fact = _fact_value(facts, tags, currency, target_end, instantaneous)
            if provider_value is None or sec_fact is None:
                continue
            sec_value = sec_fact["value"]
            tolerance = max(abs(sec_value) * 0.005, 1.0)
            difference = provider_value - sec_value
            matched = abs(difference) <= tolerance
            check = {
                "metric": name,
                "matched": matched,
                "provider_value": provider_value,
                "sec_value": sec_value,
                "difference": difference,
                "sec_tag": sec_fact["tag"],
                "sec_period_end": sec_fact["end"],
                "sec_form": sec_fact["form"],
                "accession_number": sec_fact["accession_number"],
            }
            checks.append(check)
            if not matched:
                mismatches.append(check)

        result = {
            "status": "matched" if checks and not mismatches else ("mismatch" if mismatches else "unavailable"),
            "checked": len(checks),
            "matched": len(checks) - len(mismatches),
            "mismatches": mismatches,
            "checks": checks,
            "source": "SEC Company Facts",
            "scope": "Latest-quarter core statement facts only",
        }
        if not checks:
            result["reason"] = "No comparable standardized SEC facts were found for the latest provider quarter."
    except Exception as exc:
        result = {
            "status": "unavailable",
            "checked": 0,
            "matched": 0,
            "mismatches": [],
            "reason": f"SEC numeric cross-check was unavailable: {exc}",
        }

    _CACHE[cache_key] = {"timestamp": time.time(), "data": result}
    return result
