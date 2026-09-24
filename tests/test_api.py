import pytest
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient
from main import app, prepare_charts_data, calculate_dividend_yield

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "StatementIQ Engine"}


def test_root_favicon_is_served_locally():
    response = client.get("/favicon.svg")
    assert response.status_code == 200
    assert "svg" in response.headers["content-type"]

def test_presets_endpoint():
    response = client.get("/api/presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert "Apple Inc. (AAPL)" in data["presets"]

def test_analyze_endpoint_aapl():
    response = client.get("/api/analyze?ticker=AAPL")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert "metrics" in data
    assert "ai_insights" in data
    assert "charts" in data
    assert "statements" in data
    assert "advanced_metrics" in data["metrics"]
    assert "statement_analysis" in data
    assert "sector_analysis" in data
    assert "filing_disclosure_review" in data


def test_analyze_endpoint_rejects_malformed_ticker():
    response = client.get("/api/analyze", params={"ticker": "AAPL<script>"})
    assert response.status_code == 400
    assert "valid public-company ticker" in response.json()["detail"]

def test_analyze_endpoint_jpm_financial_sector():
    response = client.get("/api/analyze?ticker=JPM")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "JPM"
    assert data["metrics"]["is_financial_sector"] is True
    evals = data["metrics"]["ratio_evaluations"]
    assert evals["current_ratio"]["status"] == "N/A"

def test_download_pdf_endpoint():
    payload = {"symbol": "MSFT"}
    
    response = client.post("/api/download-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 1000


def test_download_pdf_rejects_client_supplied_financial_numbers():
    response = client.post("/api/download-pdf", json={
        "symbol": "MSFT",
        "metrics": {"health_score": 100},
    })
    assert response.status_code == 422


def test_chart_missing_values_remain_null():
    period = pd.Timestamp("2025-01-01")
    income = pd.DataFrame({period: [100e9, None]}, index=["Total Revenue", "Net Income"])
    balance = pd.DataFrame({period: [None, None]}, index=["Cash And Cash Equivalents", "Total Debt"])

    charts = prepare_charts_data(income, balance)
    perf = charts["financial_performance"]
    cash_debt = charts["cash_vs_debt"]
    assert perf["revenue"] == [100.0]
    assert perf["net_income"] == [None]
    assert perf["gross_margin"] == [None]
    assert perf["net_margin"] == [None]
    assert cash_debt["cash"] == [None]
    assert cash_debt["debt"] == [None]


def test_frontend_contains_no_numeric_fallbacks():
    app_js = (Path(__file__).parents[1] / "static" / "app.js").read_text()
    assert "market_cap * 1.1" not in app_js
    assert 'else "0.55%"' not in app_js
    assert 'value !== null && value !== undefined && value !== ""' in app_js
    assert 'return "percent"' in app_js
    assert 'return "shares"' in app_js
    assert "renderSupportingAnalysis" in app_js
    assert "renderStatementAnalysis" in app_js
    assert "renderSectorAnalysis" in app_js
    assert "renderFilingReview" in app_js


def test_dividend_yield_uses_rate_over_price_not_ambiguous_provider_units():
    info = {"dividendRate": 1.04, "dividendYield": 0.33}
    assert calculate_dividend_yield(info, 332.0) == pytest.approx(1.04 / 332.0)
    assert calculate_dividend_yield({"dividendYield": 0.33}, 332.0) is None
