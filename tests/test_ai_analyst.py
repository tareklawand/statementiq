import pytest
from ai_analyst import generate_ai_insights, generate_custom_ticker_insights

def test_ai_insights_structure():
    ratios_summary = {
        "net_margin": {"name": "Net Margin", "value": 0.25, "status": "Healthy", "target": "Healthy ≥ 15%"},
        "pe_ratio": {"name": "TTM P/E Ratio", "value": 20.0, "status": "Healthy", "target": "Healthy ≤ 25.0"},
        "debt_to_equity": {"name": "Debt-to-Equity", "value": 1.2, "status": "Healthy", "target": "Healthy ≤ 1.50"}
    }
    
    res = generate_ai_insights("Microsoft Corporation", "MSFT", 85, ratios_summary)
    
    assert "executive_summary" in res
    assert "top_strengths" in res
    assert "top_weaknesses" in res
    assert "score_explanation" in res
    
    assert len(res["top_strengths"]) <= 3
    assert len(res["top_weaknesses"]) <= 3
    assert "0000320193-25-000079" not in res["score_explanation"] # No hardcoded Apple accession leak for MSFT!

def test_fallback_insights_no_gemini_key():
    ratios_summary = {
        "current_ratio": {"name": "Current Ratio", "value": 0.85, "status": "Warning", "target": "Healthy ≥ 1.50"},
        "roe": {"name": "Return on Equity", "value": 0.22, "status": "Healthy", "target": "Healthy ≥ 15%"}
    }
    
    res = generate_custom_ticker_insights("Tesla, Inc.", "TSLA", 65, ratios_summary)
    assert "Tesla, Inc. (TSLA)" in res["executive_summary"]
    assert len(res["top_strengths"]) >= 1
    assert len(res["top_weaknesses"]) >= 1
