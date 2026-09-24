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
            "StatementIQ/1.0 statementiq-lb.com",
        ),
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _load_ticker_map() -> Dict[str, Dict[str, Any]]:
    global _TICKER_MAP, _TICKER_MAP_FETCHED_AT
    now = time.time()
    with _LOCK:
        if _TICKER_MAP and now - _TICKER_MAP_FETCHED_AT < TICKER_MAP_TTL:
            return _TICKER_MAP

        response = requests.get(SEC_TICKER_URL, headers=_headers(), timeout=8)
        if response.status_code in {403, 429}:
            response = requests.get(
                os.environ.get(
                    "SEC_TICKER_MAP_PROXY",
                    "https://statementiq-lb.com/api/sec-ticker-map",
                ),
                headers={"Accept": "application/json"},
                timeout=15,
            )
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


def _filing_url(cik: str, accession: Any, primary_document: Any) -> Optional[str]:
    accession_compact = str(accession or "").replace("-", "")
    if not accession_compact or not primary_document:
        return None
    return (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_compact}/{primary_document}"
    )


def _filing_record(recent: Dict[str, Any], index: int, cik: str) -> Dict[str, Any]:
    accession = _value_at(recent.get("accessionNumber"), index)
    primary_document = _value_at(recent.get("primaryDocument"), index)
    return {
        "form": _value_at(recent.get("form"), index),
        "filed_date": _value_at(recent.get("filingDate"), index),
        "report_period": _value_at(recent.get("reportDate"), index),
        "items": _value_at(recent.get("items"), index),
        "accession_number": accession,
        "filing_url": _filing_url(cik, accession, primary_document),
    }


def _latest_filing(recent: Dict[str, Any], cik: str, forms: set) -> Optional[Dict[str, Any]]:
    matching = [
        index for index, form in enumerate(recent.get("form") or [])
        if form in forms
    ]
    if not matching:
        return None
    index = max(
        matching,
        key=lambda position: str(_value_at(recent.get("filingDate"), position) or ""),
    )
    return _filing_record(recent, index, cik)


def _filing_signals(recent: Dict[str, Any], cik: str) -> list:
    """Return only signals that can be identified from official form/item codes."""
    signals = []
    forms = recent.get("form") or []
    for index, form in enumerate(forms):
        filed_date = str(_value_at(recent.get("filingDate"), index) or "")
        if filed_date and filed_date < "2023-01-01":
            continue
        items = str(_value_at(recent.get("items"), index) or "")
        signal_type = None
        title = None
        severity = "review"
        if form == "8-K" and "4.02" in items:
            signal_type = "non_reliance_restatement"
            title = "Non-reliance or restatement disclosure (Form 8-K Item 4.02)"
            severity = "high"
        elif form == "8-K" and "4.01" in items:
            signal_type = "auditor_change"
            title = "Change in certifying accountant (Form 8-K Item 4.01)"
        elif form in {"10-K/A", "10-Q/A", "20-F/A", "40-F/A"}:
            signal_type = "amended_periodic_filing"
            title = f"Amended periodic filing ({form})"
        if not signal_type:
            continue
        record = _filing_record(recent, index, cik)
        record.update({"type": signal_type, "title": title, "severity": severity})
        signals.append(record)
    return sorted(signals, key=lambda item: str(item.get("filed_date") or ""), reverse=True)[:12]


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
                filing_url = _filing_url(entry["cik"], accession, primary_document)
                result = {
                    "status": "verified",
                    "registrant": payload.get("name") or entry.get("title"),
                    "cik": entry["cik"],
                    "form": _value_at(forms, chosen_index),
                    "filed_date": _value_at(recent.get("filingDate"), chosen_index),
                    "report_period": _value_at(recent.get("reportDate"), chosen_index),
                    "accession_number": accession,
                    "filing_url": filing_url,
                    "key_filings": {
                        "annual": _latest_filing(recent, entry["cik"], {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}),
                        "quarterly": _latest_filing(recent, entry["cik"], {"10-Q", "10-Q/A"}),
                        "current_report": _latest_filing(recent, entry["cik"], {"8-K", "6-K"}),
                    },
                    "filing_signals": _filing_signals(recent, entry["cik"]),
                    "signal_scope": (
                        "Signals use official SEC form and item codes for recent amendments, "
                        "Item 4.02 non-reliance/restatement disclosures, and Item 4.01 auditor changes. "
                        "Absence of a signal is not assurance that no accounting issue exists."
                    ),
                }
    except Exception as exc:
        result = {
            "status": "unavailable",
            "reason": f"SEC recency validation was unavailable: {exc}",
        }

    _FILING_CACHE[normalized] = {"timestamp": now, "data": result}
    return result
