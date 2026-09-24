import pytest
import pandas as pd
import numpy as np
from metrics_calculator import compute_metrics, evaluate_connected_financial_model, evaluate_financial_health

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
    # An income statement and balance sheet without cash-flow or trend data do
    # not provide enough connected evidence for a responsible health score.
    assert res["health_score"] is None
    assert res["health_status"] == "Insufficient Data"
    
    evals = res["ratio_evaluations"]
    assert evals["current_ratio"]["status"] in ["Healthy", "Caution", "Warning"]
    assert evals["gross_margin"]["status"] == "Context"
    assert evals["gross_margin"]["score_model"] == "context"
    assert evals["pe_ratio"]["value"] == 25.0

def test_financial_institution_sector_rules():
    data = {
        "symbol": "JPM",
        "info": {
                "symbol": "JPM",
                "sector": "Financial Services",
                "industry": "Banks - Diversified",
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
    
    # Financial sector leaves industrial diagnostics visible as context but
    # withholds a misleading health score until regulatory metrics are available.
    assert evals["net_margin"]["status"] == "Context"
    assert evals["roa"]["status"] == "Context"
    assert res["health_score"] is None
    assert res["health_status"] == "Sector Model Required"
    assert "regulatory capital" in res["score_coverage"]["withheld_reason"]
    assert res["applicability_profile"]["key"] == "financial_institution"

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


def _complete_connected_model_inputs():
    ratios = {
        "current_ratio": 1.8,
        "quick_ratio": 1.2,
        "debt_to_equity": 0.8,
        "gross_margin": 0.42,
        "net_margin": 0.16,
        "roe": 0.18,
        "roa": 0.09,
        "asset_turnover": 0.7,
        "pe_ratio": 22.0,
        "ev_ebitda": 13.0,
    }
    supplemental = {
        "cash_ratio": 0.6,
        "interest_coverage": 7.0,
        "debt_to_ebitda": 1.7,
        "net_debt_to_ebitda": 1.1,
        "operating_margin": 0.18,
        "free_cash_flow_margin": 0.12,
        "free_cash_flow_yield": 0.055,
        "cash_conversion": 1.1,
        "annual_revenue_growth": 0.07,
        "annual_net_income_growth": 0.06,
        "diluted_share_change": -0.01,
    }
    advanced = {
        "roic": 0.14,
        "operating_cash_flow_margin": 0.15,
        "accrual_ratio": -0.01,
        "annual_eps_growth": 0.08,
        "annual_fcf_growth": 0.07,
        "revenue_per_share_growth": 0.08,
        "effective_tax_rate": 0.21,
        "price_to_sales": 3.0,
        "price_to_book": 2.5,
        "ev_to_sales": 3.5,
    }
    return ratios, supplemental, advanced


def test_connected_model_separates_health_from_valuation():
    ratios, supplemental, advanced = _complete_connected_model_inputs()
    result = evaluate_connected_financial_model(
        ratios, supplemental, advanced, sector="Technology", industry="Software - Infrastructure"
    )
    assert result["score"] is not None
    assert result["valuation_score"] is not None
    assert result["coverage"]["coverage_percent"] == pytest.approx(1.0)
    assert result["coverage"]["score_range"] == {"low": result["score"], "high": result["score"]}
    assert sum(
        item["weight"] for item in result["evaluations"].values()
        if item["score_model"] == "financial_health"
    ) == pytest.approx(1.0)

    expensive_ratios = {**ratios, "pe_ratio": 100.0, "ev_ebitda": 50.0}
    expensive_advanced = {**advanced, "price_to_sales": 20.0, "price_to_book": 12.0, "ev_to_sales": 18.0}
    expensive_supplemental = {**supplemental, "free_cash_flow_yield": 0.005}
    expensive = evaluate_connected_financial_model(
        expensive_ratios, expensive_supplemental, expensive_advanced,
        sector="Technology", industry="Software - Infrastructure",
    )
    assert expensive["score"] == result["score"]
    assert expensive["valuation_score"] < result["valuation_score"]


def test_health_score_requires_evidence_in_every_component():
    ratios, supplemental, advanced = _complete_connected_model_inputs()
    for key in ("annual_revenue_growth", "annual_net_income_growth", "diluted_share_change"):
        supplemental[key] = None
    for key in ("annual_eps_growth", "annual_fcf_growth", "revenue_per_share_growth"):
        advanced[key] = None
    result = evaluate_connected_financial_model(
        ratios, supplemental, advanced, sector="Technology", industry="Software - Infrastructure"
    )
    assert result["coverage"]["coverage_percent"] == pytest.approx(0.85)
    assert result["coverage"]["covered_component_count"] == 4
    assert result["score"] is None
    assert result["coverage"]["score_range"] is None


def test_company_profile_controls_applicability_for_any_ticker_metadata():
    ratios, supplemental, advanced = _complete_connected_model_inputs()
    bank = evaluate_connected_financial_model(
        ratios, supplemental, advanced, is_financial_sector=True,
        sector="Financial Services", industry="Banks - Regional",
    )
    assert bank["score"] is None
    assert bank["status"] == "Sector Model Required"
    assert bank["applicability_profile"]["key"] == "financial_institution"
    assert bank["evaluations"]["ev_ebitda"]["score_model"] == "context"

    reit = evaluate_connected_financial_model(
        ratios, supplemental, advanced, sector="Real Estate", industry="REIT - Retail",
    )
    assert reit["score"] is None
    assert reit["valuation_score"] is None
    assert reit["applicability_profile"]["key"] == "reit"


def test_utility_profile_uses_utility_adjusted_leverage_ranges():
    ratios, supplemental, advanced = _complete_connected_model_inputs()
    ratios["debt_to_equity"] = 2.5
    utility = evaluate_connected_financial_model(
        ratios, supplemental, advanced, sector="Utilities", industry="Utilities - Regulated Electric",
    )
    assert utility["applicability_profile"]["key"] == "regulated_utility"
    assert utility["evaluations"]["debt_to_equity"]["status"] == "Caution"
    assert "utility-adjusted" in utility["evaluations"]["debt_to_equity"]["target"]
