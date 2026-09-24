"""Conservative automated phrase review of the latest annual SEC filing."""

from __future__ import annotations

import html
import os
import re
import threading
import time
from typing import Any, Dict

import requests


_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCK = threading.Lock()
_CACHE_TTL = 6 * 60 * 60

_TOPICS = (
    (
        "material_weakness",
        "Affirmative material-weakness language",
        "risk_phrase",
        (
            r"(?:we|management) (?:have |has )?identified (?:a|one or more) material weakness(?:es)?",
            r"there (?:is|are) (?:a|one or more) material weakness(?:es)?",
            r"internal control over financial reporting was not effective",
        ),
    ),
    ("going_concern", "Going-concern language", "risk_phrase", (r"substantial doubt.{0,180}continue as a going concern",)),
    ("critical_audit_matter", "Critical audit matter section", "audit_topic", (r"critical audit matter",)),
    ("debt_maturities", "Debt maturities / contractual obligations", "disclosure_topic", (r"debt maturit", r"contractual obligations")),
    ("leases", "Lease disclosures", "disclosure_topic", (r"operating leases?", r"finance leases?")),
    ("pensions", "Pension / postretirement disclosures", "disclosure_topic", (r"defined benefit pension", r"postretirement benefit")),
    ("legal_contingencies", "Legal proceedings / contingencies", "disclosure_topic", (r"legal proceedings", r"commitments and contingencies")),
    ("goodwill_impairment", "Goodwill / impairment disclosures", "disclosure_topic", (r"goodwill.{0,100}impair", r"impairment.{0,100}goodwill")),
    ("related_parties", "Related-party disclosures", "disclosure_topic", (r"related part(?:y|ies)",)),
    ("revenue_recognition", "Revenue-recognition policy", "disclosure_topic", (r"revenue recognition",)),
    ("segments", "Segment reporting", "disclosure_topic", (r"reportable segments?", r"segment information")),
    ("acquisitions", "Acquisition / business-combination disclosures", "disclosure_topic", (r"business combinations?", r"acquisition date")),
    ("discontinued_operations", "Discontinued-operations disclosures", "disclosure_topic", (r"discontinued operations?",)),
)


def _plain_text(document: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", document)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip().lower()


def analyze_filing_text(document: str) -> Dict[str, Any]:
    text = _plain_text(document)
    topics = []
    for key, label, classification, patterns in _TOPICS:
        located = any(re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)
        topics.append({
            "key": key,
            "label": label,
            "classification": classification,
            "status": "located" if located else "not_located_by_phrase_scan",
        })
    return {
        "status": "analyzed",
        "topics": topics,
        "scope": (
            "Automated phrase-location review of the latest annual filing. A located phrase is a prompt to read the related note, "
            "not a conclusion that a problem exists. A phrase not located does not prove the disclosure is absent."
        ),
    }


def scan_annual_filing(filing_url: str) -> Dict[str, Any]:
    if not filing_url or not filing_url.startswith("https://www.sec.gov/"):
        return {"status": "not_applicable", "reason": "No official SEC annual filing URL was available."}
    now = time.time()
    with _LOCK:
        cached = _CACHE.get(filing_url)
        if cached and now - cached["timestamp"] < _CACHE_TTL:
            return cached["data"]
    try:
        response = requests.get(
            filing_url,
            headers={
                "User-Agent": os.environ.get(
                    "SEC_USER_AGENT",
                    "StatementIQ/1.0 statementiq-lb.com",
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=10,
        )
        response.raise_for_status()
        if len(response.content) > 20 * 1024 * 1024:
            raise ValueError("Annual filing exceeded the automated review size limit.")
        result = analyze_filing_text(response.text)
        result["filing_url"] = filing_url
    except Exception as exc:
        result = {
            "status": "unavailable",
            "reason": f"Annual filing phrase review was unavailable: {exc}",
            "filing_url": filing_url,
        }
    with _LOCK:
        _CACHE[filing_url] = {"timestamp": now, "data": result}
    return result
