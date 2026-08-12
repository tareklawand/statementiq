import pytest
from fastapi.testclient import TestClient
from main import app

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
