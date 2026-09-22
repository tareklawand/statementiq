import pandas as pd
import pytest

import data_fetcher
from main import prepare_charts_data
from metrics_calculator import compute_metrics, evaluate_financial_health


def frame(columns, rows):
    return pd.DataFrame(columns, index=rows)


def test_statement_periods_are_normalized_newest_first_and_deduplicated():
    raw = pd.DataFrame(
        [[1.0, 3.0, 2.0, 99.0]],
        index=["Total Revenue"],
        columns=["2024-12-31", "2026-12-31", "2025-12-31", "2025-12-31"],
    )
    normalized = data_fetcher.normalize_statement(raw)
    assert list(normalized.columns) == [
        pd.Timestamp("2026-12-31"),
        pd.Timestamp("2025-12-31"),
        pd.Timestamp("2024-12-31"),
    ]
    assert normalized.iloc[0].tolist() == [3.0, 2.0, 1.0]


def test_fiscal_calendar_normalization_does_not_create_a_false_staleness_hold():
    assert data_fetcher._period_is_materially_newer("2026-07-03", "2026-06-30") is False
    assert data_fetcher._period_is_materially_newer("2026-09-30", "2026-06-30") is True


def test_metrics_use_ttm_flows_latest_quarter_balance_and_year_ago_average():
    q_dates = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30"])
    data = {
        "symbol": "TEST",
        "info": {
            "symbol": "TEST",
            "sector": "Technology",
            "industry": "Software - Application",
            "regularMarketPrice": 20.0,
            "marketCap": 2000.0,
            "epsTrailingTwelveMonths": 2.0,
        },
        "income_stmt": pd.DataFrame(
            {pd.Timestamp("2025-12-31"): [900.0, 180.0], pd.Timestamp("2024-12-31"): [800.0, 160.0]},
            index=["Total Revenue", "Net Income"],
        ),
        "analysis_income_stmt": pd.DataFrame(
            {pd.Timestamp("2026-06-30"): [1000.0, 400.0, 200.0, 150.0, 220.0]},
            index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "EBITDA"],
        ),
        "analysis_balance_sheet": pd.DataFrame(
            {
                q_dates[0]: [500.0, 200.0, 100.0, 50.0, 25.0, 120.0, 250.0],
                q_dates[1]: [490.0, 195.0, 98.0, 48.0, 24.0, 118.0, 245.0],
                q_dates[2]: [480.0, 190.0, 96.0, 46.0, 23.0, 116.0, 240.0],
                q_dates[3]: [470.0, 185.0, 94.0, 44.0, 22.0, 114.0, 235.0],
                q_dates[4]: [400.0, 180.0, 90.0, 40.0, 20.0, 100.0, 200.0],
            },
            index=["Total Assets", "Current Assets", "Current Liabilities", "Cash And Cash Equivalents", "Receivables", "Total Debt", "Common Stock Equity"],
        ),
        "analysis_cash_flow": pd.DataFrame(
            {pd.Timestamp("2026-06-30"): [180.0, -30.0, 150.0, 20.0]},
            index=["Operating Cash Flow", "Capital Expenditure", "Free Cash Flow", "Depreciation And Amortization"],
        ),
        "analysis_basis": {
            "income": "trailing_twelve_months",
            "balance_sheet": "latest_quarter",
            "cash_flow": "trailing_twelve_months",
        },
    }

    result = compute_metrics(data)
    assert result["raw_financials"]["revenue"] == 1000.0
    assert result["raw_financials"]["total_assets"] == 500.0
    assert result["ratios"]["roa"] == pytest.approx(150.0 / 450.0)
    assert result["ratios"]["roe"] == pytest.approx(150.0 / 225.0)
    assert result["supplemental_metrics"]["free_cash_flow"] == 150.0
    assert result["supplemental_metrics"]["free_cash_flow_margin"] == pytest.approx(0.15)


def test_score_is_withheld_when_ratio_coverage_is_too_low():
    ratios = {
        "current_ratio": 2.0,
        "quick_ratio": None,
        "debt_to_equity": None,
        "gross_margin": None,
        "net_margin": None,
        "roe": None,
        "roa": None,
        "asset_turnover": None,
        "pe_ratio": None,
        "ev_ebitda": None,
    }
    result = evaluate_financial_health(ratios)
    assert result["score"] is None
    assert result["status"] == "Insufficient Data"
    assert result["coverage"]["applicable_ratio_count"] == 1
    assert result["coverage"]["minimum_required"] == 6


def test_ttm_returns_are_not_computed_from_prior_quarter_when_year_ago_balance_is_missing():
    dates = pd.to_datetime(["2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30"])
    data = {
        "symbol": "SHORT_HISTORY",
        "info": {"sector": "Technology", "industry": "Software"},
        "analysis_income_stmt": pd.DataFrame(
            {dates[0]: [100.0, 20.0]}, index=["Total Revenue", "Net Income"]
        ),
        "analysis_balance_sheet": pd.DataFrame(
            {date: [200.0, 100.0] for date in dates},
            index=["Total Assets", "Common Stock Equity"],
        ),
        "analysis_cash_flow": pd.DataFrame(),
        "analysis_basis": {"income": "trailing_twelve_months", "balance_sheet": "latest_quarter"},
        "income_stmt": pd.DataFrame(),
    }
    result = compute_metrics(data)
    assert result["ratios"]["roa"] is None
    assert result["ratios"]["roe"] is None


def test_payment_network_is_not_misclassified_as_a_bank():
    data = {
        "symbol": "V",
        "info": {"symbol": "V", "sector": "Financial Services", "industry": "Credit Services"},
        "income_stmt": pd.DataFrame(),
        "balance_sheet": pd.DataFrame(),
        "cash_flow": pd.DataFrame(),
    }
    result = compute_metrics(data)
    assert result["is_financial_sector"] is False


def test_enterprise_value_is_withheld_when_market_and_statement_currencies_differ():
    period = pd.Timestamp("2026-06-30")
    data = {
        "symbol": "ADR",
        "info": {
            "sector": "Technology",
            "industry": "Software",
            "currency": "USD",
            "financialCurrency": "CNY",
            "marketCap": 1000.0,
        },
        "income_stmt": pd.DataFrame({period: [100.0]}, index=["Total Revenue"]),
        "balance_sheet": pd.DataFrame(
            {period: [50.0, 20.0]}, index=["Total Debt", "Cash Cash Equivalents And Short Term Investments"]
        ),
        "cash_flow": pd.DataFrame(),
    }
    result = compute_metrics(data)
    assert result["ev_breakdown"]["currencies_compatible"] is False
    assert result["ev_breakdown"]["enterprise_value_std"] is None
    assert result["ratios"]["ev_ebitda"] is None


def test_cash_debt_chart_sums_debt_components_without_total_debt():
    period = pd.Timestamp("2026-06-30")
    income = pd.DataFrame({period: [100.0]}, index=["Total Revenue"])
    balance = pd.DataFrame(
        {period: [20e9, 5e9, 30e9, 70e9]},
        index=["Cash And Cash Equivalents", "Other Short Term Investments", "Current Debt", "Long Term Debt"],
    )
    chart = prepare_charts_data(income, balance)["cash_vs_debt"]
    assert chart["cash"] == [25.0]
    assert chart["debt"] == [100.0]


def test_integrity_hold_suppresses_headline_score_without_hiding_ratios():
    period = pd.Timestamp("2026-06-30")
    data = {
        "symbol": "CHECK",
        "info": {
            "sector": "Technology",
            "industry": "Software",
            "regularMarketPrice": 20.0,
            "marketCap": 1000.0,
            "epsTrailingTwelveMonths": 2.0,
        },
        "income_stmt": pd.DataFrame(
            {period: [100.0, 50.0, 25.0, 20.0]},
            index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
        ),
        "balance_sheet": pd.DataFrame(
            {
                period: [200.0, 80.0, 40.0, 20.0, 10.0, 30.0, 100.0],
                pd.Timestamp("2025-06-30"): [180.0, 70.0, 35.0, 18.0, 9.0, 28.0, 90.0],
            },
            index=["Total Assets", "Current Assets", "Current Liabilities", "Cash And Cash Equivalents", "Receivables", "Total Debt", "Common Stock Equity"],
        ),
        "cash_flow": pd.DataFrame(),
        "integrity_hold_reason": "Provider and SEC facts did not agree.",
    }
    result = compute_metrics(data)
    assert result["ratio_evaluations"]["current_ratio"]["value"] == 2.0
    assert result["health_score"] is None
    assert result["health_status"] == "Verification Hold"
    assert result["score_coverage"]["withheld_reason"] == "Provider and SEC facts did not agree."


def test_calculation_coverage_lists_missing_inputs_instead_of_estimating_them():
    result = compute_metrics({"symbol": "EMPTY", "info": {}, "income_stmt": pd.DataFrame(), "balance_sheet": pd.DataFrame(), "cash_flow": pd.DataFrame()})
    coverage = result["calculation_coverage"]
    assert coverage["available_core_input_count"] == 0
    assert coverage["core_input_count"] == 14
    assert "revenue" in coverage["missing_core_inputs"]
    assert "total_debt" in coverage["missing_core_inputs"]


@pytest.mark.parametrize("reported_capex", [-30.0, 30.0])
def test_free_cash_flow_normalizes_capex_sign_conventions(reported_capex):
    period = pd.Timestamp("2026-06-30")
    data = {
        "symbol": "CAPEX",
        "info": {"sector": "Industrials"},
        "analysis_income_stmt": pd.DataFrame({period: [1000.0]}, index=["Total Revenue"]),
        "analysis_balance_sheet": pd.DataFrame(),
        "analysis_cash_flow": pd.DataFrame(
            {period: [180.0, reported_capex]},
            index=["Operating Cash Flow", "Capital Expenditure"],
        ),
        "income_stmt": pd.DataFrame(),
        "analysis_basis": {"income": "trailing_twelve_months"},
    }
    result = compute_metrics(data)
    assert result["supplemental_metrics"]["free_cash_flow"] == 150.0
    assert result["supplemental_metrics"]["free_cash_flow_method"] == "operating_cash_flow_less_capital_spending"


def test_pe_uses_statement_diluted_eps_when_market_eps_is_missing():
    period = pd.Timestamp("2026-06-30")
    data = {
        "symbol": "EPS",
        "info": {"sector": "Technology", "regularMarketPrice": 50.0},
        "analysis_income_stmt": pd.DataFrame({period: [2.5]}, index=["Diluted EPS"]),
        "analysis_balance_sheet": pd.DataFrame(),
        "analysis_cash_flow": pd.DataFrame(),
        "income_stmt": pd.DataFrame(),
    }
    result = compute_metrics(data)
    assert result["ratios"]["pe_ratio"] == 20.0
