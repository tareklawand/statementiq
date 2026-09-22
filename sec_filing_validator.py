"""Read-only SEC filing metadata used to validate statement recency.

The financial engine does not replace statement values with SEC data in this
module.  It uses EDGAR's official submissions feed to answer a narrower and
important question: is the provider statement period aligned with the latest
10-K/10-Q filed by a U.S. issuer?
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, Optional

import requests


_TICKER_MAP: Dict[str, Dict[str, Any]] = {}
_TICKER_MAP_FETCHED_AT = 0.0
_FILING_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()

TICKER_MAP_TTL = 24 * 60 * 60
FILING_CACHE_TTL = 15 * 60
SEC_TICKER_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"


def _headers() -> Dict[str, str]:
    # SEC asks automated clients to identify themselves. Operators can provide
    # a contact email through SEC_USER_AGENT without changing application code.
    return {
        "User-Agent": os.environ.get(
            "SEC_USER_AGENT",
            "StatementIQ/1.0 (statementiq-lb.com; financial-data validation)",
        ),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
    }


def _load_ticker_map() -> Dict[str, Dict[str, Any]]:
    global _TICKER_MAP, _TICKER_MAP_FETCHED_AT
    now = time.time()
    with _LOCK:
        if _TICKER_MAP and now - _TICKER_MAP_FETCHED_AT < TICKER_MAP_TTL:
            return _TICKER_MAP

        response = requests.get(SEC_TICKER_URL, headers=_headers(), timeout=8)
        response.raise_for_status()
        payload = response.json()
        mapped: Dict[str, Dict[str, Any]] = {}
        for entry in payload.values():
            ticker = str(entry.get("ticker") or "").upper()
            cik = entry.get("cik_str")
            if ticker and cik is not None:
                mapped[ticker] = {
                    "ticker": ticker,
                    "cik": str(cik).zfill(10),
                    "title": entry.get("title"),
                }
        _TICKER_MAP = mapped
        _TICKER_MAP_FETCHED_AT = now
        return _TICKER_MAP


def _value_at(values: Any, index: int) -> Optional[Any]:
    if isinstance(values, list) and index < len(values):
        return values[index]
    return None


def get_latest_sec_filing(symbol: str, cik_hint: Optional[str] = None) -> Dict[str, Any]:
    """Return latest official 10-K/10-Q metadata, or a non-fatal status.

    A missing SEC match is normal for many non-U.S. issuers. Network failures
    are surfaced as an unavailable validation rather than failing analysis.
    """

    normalized = symbol.strip().upper().replace("-", ".")
    now = time.time()
    cached = _FILING_CACHE.get(normalized)
    if (
        cached
        and now - cached["timestamp"] < FILING_CACHE_TTL
        and not (cik_hint and cached["data"].get("status") != "verified")
    ):
        return cached["data"]

    try:
        entry = None
        if cik_hint:
            digits = "".join(character for character in str(cik_hint) if character.isdigit())
            if digits:
                entry = {"ticker": normalized, "cik": digits.zfill(10), "title": None}
        if not entry:
            entry = _load_ticker_map().get(normalized)
        if not entry:
            result = {
                "status": "not_applicable",
                "reason": "No SEC registrant match was found for this ticker.",
            }
        else:
            response = requests.get(
                SEC_SUBMISSIONS_URL.format(cik=entry["cik"]),
                headers=_headers(),
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json()
            recent = (payload.get("filings") or {}).get("recent") or {}
            forms = recent.get("form") or []
            periodic_forms = {
                "10-K", "10-Q", "10-K/A", "10-Q/A",
                "20-F", "20-F/A", "40-F", "40-F/A",
            }
            candidate_indices = [
                i for i, form in enumerate(forms)
                if form in periodic_forms
            ]
            chosen_index = max(
                candidate_indices,
                key=lambda i: (
                    str(_value_at(recent.get("reportDate"), i) or ""),
                    str(_value_at(recent.get("filingDate"), i) or ""),
                ),
                default=None,
            )
            if chosen_index is None:
                result = {
                    "status": "unavailable",
                    "reason": "No recent 10-K or 10-Q was present in the SEC submissions response.",
                    "cik": entry["cik"],
                }
            else:
                accession = _value_at(recent.get("accessionNumber"), chosen_index)
                primary_document = _value_at(recent.get("primaryDocument"), chosen_index)
                accession_compact = str(accession or "").replace("-", "")
                filing_url = None
                if accession_compact and primary_document:
                    filing_url = (
                        f"https://www.sec.gov/Archives/edgar/data/{int(entry['cik'])}/"
                        f"{accession_compact}/{primary_document}"
                    )
                result = {
                    "status": "verified",
                    "registrant": payload.get("name") or entry.get("title"),
                    "cik": entry["cik"],
                    "form": _value_at(forms, chosen_index),
                    "filed_date": _value_at(recent.get("filingDate"), chosen_index),
                    "report_period": _value_at(recent.get("reportDate"), chosen_index),
                    "accession_number": accession,
                    "filing_url": filing_url,
                }
    except Exception as exc:
        result = {
            "status": "unavailable",
            "reason": f"SEC recency validation was unavailable: {exc}",
        }

    _FILING_CACHE[normalized] = {"timestamp": now, "data": result}
    return result
