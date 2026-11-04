import pandas as pd
import pytest
from fastapi.testclient import TestClient
import evidence_snapshot
import main


def test_sec_evidence_does_not_fetch_market_quotes(monkeypatch):
    filing = {"status": "verified", "cik": "0000123456", "registrant": "Example Inc.", "sic": "3571",
              "accession_number": "0000123456-26-000001", "report_period": "2025-12-31"}
    frame = pd.DataFrame({pd.Timestamp("2025-12-31"): [100, 10]}, index=["Total Revenue", "Net Income"])
    monkeypatch.setattr(evidence_snapshot, "get_latest_sec_filing", lambda symbol, force_refresh: filing)
    monkeypatch.setattr(evidence_snapshot, "import_latest_sec_statements", lambda value: {
        "status": "imported", "currency": "USD", "basis": "latest_annual", "report_period": "2025-12-31",
        "frames": {"income_stmt": frame}, "integrity_checks": [], "warnings": []})
    monkeypatch.setattr(main, "fetch_stock_data", lambda *a, **k: pytest.fail("SEC archive must not use the quote/data-provider route"))
    monkeypatch.setattr(main, "scan_annual_filing", lambda *a, **k: pytest.fail("Text review is separate from numeric evidence"))
    result = TestClient(main.app).get("/api/research/filing-snapshot?ticker=example")
    assert result.status_code == 200
    data = result.json()
    assert data["symbol"] == "EXAMPLE"
    assert data["purpose"] == "public_sec_filing_evidence"
    assert data["info"]["price"] is None
    assert data["info"]["market_cap"] is None
    assert data["info"]["enterprise_value"] is None
    assert data["metrics"]["valuation_score"] is None
    assert data["data_quality"]["market_provider"] is None
    assert data["data_quality"]["statement_provider"] == "SEC Company Facts"
    assert len(data["methodology"]["code_sha256"]) == 64
    assert len(data["input_sha256"]) == 64


def test_incomplete_sec_evidence_is_not_estimated_or_saved(monkeypatch):
    monkeypatch.setattr(evidence_snapshot, "get_latest_sec_filing", lambda *a, **k: {"status": "unavailable"})
    monkeypatch.setattr(evidence_snapshot, "import_latest_sec_statements", lambda *a: {"status": "unavailable", "reason": "Custom-only taxonomy"})
    result = TestClient(main.app).get("/api/research/filing-snapshot?ticker=EXAMPLE")
    assert result.status_code == 503
    assert "Custom-only" in result.json()["detail"]
    assert TestClient(main.app).get("/api/research/filing-snapshot?ticker=AAPL<script>").status_code == 400
