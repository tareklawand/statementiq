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

def test_analyze_endpoint_jpm_financial_sector():
    response = client.get("/api/analyze?ticker=JPM")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "JPM"
    assert data["metrics"]["is_financial_sector"] is True
    evals = data["metrics"]["ratio_evaluations"]
    assert evals["current_ratio"]["status"] == "N/A"

def test_download_pdf_endpoint():
    payload = {
        "symbol": "MSFT",
        "company_name": "Microsoft Corporation",
        "metrics": {
            "health_score": 88,
            "ev_breakdown": {"market_cap": 3000e9, "operating_income": 100e9, "total_debt": 50e9, "cash_and_short_term": 70e9},
            "raw_financials": {"revenue": 240e9, "net_income": 80e9, "current_assets": 180e9, "current_liabilities": 100e9},
            "ratio_evaluations": {
                "net_margin": {"name": "Net Margin", "category": "Profitability", "value": 0.33, "status": "Healthy", "target": "Healthy ≥ 15%", "format": "{:.1%}", "pts": 1.0, "weight": 0.10, "w_pts": 10.0}
            }
        },
        "ai_insights": {
            "executive_summary": "Microsoft is a technology powerhouse.",
            "top_strengths": ["High net margin", "Strong balance sheet"],
            "top_weaknesses": ["Valuation multiples"]
        }
    }
    
    response = client.post("/api/download-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 1000


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


def test_dividend_yield_uses_rate_over_price_not_ambiguous_provider_units():
    info = {"dividendRate": 1.04, "dividendYield": 0.33}
    assert calculate_dividend_yield(info, 332.0) == pytest.approx(1.04 / 332.0)
    assert calculate_dividend_yield({"dividendYield": 0.33}, 332.0) is None
