import pytest
import pandas as pd
import numpy as np
from metrics_calculator import compute_metrics, evaluate_financial_health

def test_industrial_company_metrics():
    data = {
        "symbol": "AAPL",
        "info": {
            "symbol": "AAPL",
            "sector": "Technology",
            "regularMarketPrice": 200.0,
            "marketCap": 3000e9,
            "epsTrailingTwelveMonths": 8.0,
        },
        "income_stmt": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [100e9, 45e9, 30e9, 25e9]
        }, index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]),
        "balance_sheet": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [200e9, 80e9, 50e9, 20e9, 10e9, 40e9, 100e9],
            pd.Timestamp("2024-01-01"): [180e9, 70e9, 45e9, 18e9, 8e9, 35e9, 90e9]
        }, index=["Total Assets", "Current Assets", "Current Liabilities", "Cash And Cash Equivalents", "Receivables", "Total Debt", "Stockholders Equity"]),
        "cash_flow": pd.DataFrame()
    }
    
    res = compute_metrics(data)
    assert res["symbol"] == "AAPL"
    assert res["is_financial_sector"] is False
    assert 0 <= res["health_score"] <= 100
    
    evals = res["ratio_evaluations"]
    assert evals["current_ratio"]["status"] in ["Healthy", "Caution", "Warning"]
    assert evals["gross_margin"]["status"] in ["Healthy", "Caution", "Warning"]
    assert evals["pe_ratio"]["value"] == 25.0

def test_financial_institution_sector_rules():
    data = {
        "symbol": "JPM",
        "info": {
            "symbol": "JPM",
            "sector": "Financial Services",
            "regularMarketPrice": 210.0,
            "marketCap": 600e9,
            "epsTrailingTwelveMonths": 17.0,
        },
        "income_stmt": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [150e9, 60e9, 50e9]
        }, index=["Total Revenue", "Operating Income", "Net Income"]),
        "balance_sheet": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [3800e9, 380e9, 320e9],
            pd.Timestamp("2024-01-01"): [3600e9, 350e9, 290e9]
        }, index=["Total Assets", "Total Debt", "Stockholders Equity"]),
        "cash_flow": pd.DataFrame()
    }
    
    res = compute_metrics(data)
    assert res["is_financial_sector"] is True
    evals = res["ratio_evaluations"]
    
    # Financial sector skips industrial-only ratios cleanly with N/A status
    assert evals["current_ratio"]["status"] == "N/A"
    assert evals["quick_ratio"]["status"] == "N/A"
    assert evals["gross_margin"]["status"] == "N/A"
    assert evals["ev_ebitda"]["status"] == "N/A"
    assert res["ev_breakdown"]["enterprise_value_std"] is None
    assert res["ratios"]["ev_ebitda"] is None
    
    # Financial sector shows applicable diagnostics but withholds a misleading
    # general-model headline score until regulatory metrics are available.
    assert evals["net_margin"]["status"] in ["Healthy", "Caution", "Warning"]
    assert evals["roa"]["status"] in ["Healthy", "Caution", "Warning"]
    assert res["health_score"] is None
    assert res["health_status"] == "Verification Hold"
    assert "sector-specific regulatory model" in res["score_coverage"]["withheld_reason"]

def test_negative_eps_not_meaningful_pe():
    data = {
        "symbol": "LOSS_CO",
        "info": {
            "symbol": "LOSS_CO",
            "sector": "Technology",
            "regularMarketPrice": 50.0,
            "marketCap": 10e9,
            "epsTrailingTwelveMonths": -2.5, # Negative EPS
        },
        "income_stmt": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [1e9, 0.4e9, -0.5e9, -0.5e9]
        }, index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]),
        "balance_sheet": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [5e9, 2e9, 1e9, 1e9, 2e9]
        }, index=["Total Assets", "Current Assets", "Current Liabilities", "Total Debt", "Stockholders Equity"]),
        "cash_flow": pd.DataFrame()
    }
    
    res = compute_metrics(data)
    evals = res["ratio_evaluations"]
    
    # P/E must be N/M (Not Meaningful) for negative EPS
    assert evals["pe_ratio"]["status"] == "N/M"
    assert evals["pe_ratio"]["value"] is None

def test_negative_equity_not_meaningful_roe_de():
    data = {
        "symbol": "NEG_EQ",
        "info": {
            "symbol": "NEG_EQ",
            "sector": "Consumer Cyclical",
            "regularMarketPrice": 15.0,
            "marketCap": 1e9,
            "epsTrailingTwelveMonths": 1.0,
        },
        "income_stmt": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [2e9, 0.8e9, 0.2e9, 0.1e9]
        }, index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]),
        "balance_sheet": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [3e9, 1e9, 2e9, 4e9, -1e9], # Negative Equity
            pd.Timestamp("2024-01-01"): [3e9, 1e9, 2e9, 4e9, -1e9]
        }, index=["Total Assets", "Current Assets", "Current Liabilities", "Total Debt", "Stockholders Equity"]),
        "cash_flow": pd.DataFrame()
    }
    
    res = compute_metrics(data)
    evals = res["ratio_evaluations"]
    
    # ROE & Debt-to-Equity must be N/M for negative equity
    assert evals["roe"]["status"] == "N/M"
    assert evals["debt_to_equity"]["status"] == "N/M"

def test_missing_data_no_fabrication():
    data = {
        "symbol": "EMPTY_CO",
        "info": {"symbol": "EMPTY_CO", "sector": "Technology"},
        "income_stmt": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cash_flow": pd.DataFrame()
    }
    
    res = compute_metrics(data)
    evals = res["ratio_evaluations"]
    for key, eval_item in evals.items():
        assert eval_item["status"] in ["N/A", "N/M"]
    assert res["health_score"] is None
    assert res["health_status"] == "Insufficient Data"
    assert res["ev_breakdown"]["total_debt"] is None
    assert res["ev_breakdown"]["cash_and_short_term"] is None
    assert res["ev_breakdown"]["enterprise_value_std"] is None
    assert res["ev_breakdown"]["ebitda"] is None


def test_missing_debt_and_da_do_not_become_zero():
    data = {
        "symbol": "NO_GUESSES",
        "info": {
            "symbol": "NO_GUESSES",
            "sector": "Technology",
            "regularMarketPrice": 10.0,
            "marketCap": 1e9,
            "epsTrailingTwelveMonths": 1.0,
        },
        "income_stmt": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [2e9, 0.8e9, 0.2e9, 0.1e9]
        }, index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"]),
        "balance_sheet": pd.DataFrame({
            pd.Timestamp("2025-01-01"): [3e9, 1e9, 0.5e9, 0.2e9, 1.5e9]
        }, index=["Total Assets", "Current Assets", "Current Liabilities", "Cash And Cash Equivalents", "Stockholders Equity"]),
        "cash_flow": pd.DataFrame(),
    }

    res = compute_metrics(data)
    assert res["ratios"]["debt_to_equity"] is None
    assert res["ratios"]["quick_ratio"] is None
    assert res["ratios"]["ev_ebitda"] is None
    assert res["ev_breakdown"]["enterprise_value_std"] is None
    assert res["ev_breakdown"]["ebitda"] is None
