from copy import deepcopy
from datetime import datetime, timezone
import pytest
from peer_comparison import compare_peers

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)

def company(symbol, pe=20):
    return {"symbol": symbol, "info": {"currency": "USD", "industry": "Software", "sector": "Technology"},
        "data_quality": {"analysis_basis": {"income": "trailing_twelve_months", "cash_flow": "trailing_twelve_months",
            "income_period_end": "2026-09-30", "balance_sheet_period_end": "2026-09-30", "cash_flow_period_end": "2026-09-30"},
            "market_data_as_of": "2026-11-03T21:00:00+00:00"},
        "metrics": {"applicability_profile": {"key": "operating_company"}, "ratios": {"pe_ratio": pe, "net_margin": .2},
            "supplemental_metrics": {"free_cash_flow_yield": -.03}}}

def metric(result, key):
    return next(row for row in result["measures"] if row["key"] == key)


def test_peer_median_excludes_anchor_and_requires_two_observations():
    result = compare_peers([company("ANCHOR", 1000), company("ONE", 10), company("TWO", 30)], now=NOW)
    assert metric(result, "pe_ratio")["peer_median"] == 20
    assert metric(result, "pe_ratio")["peer_count"] == 2
    assert metric(compare_peers([company("A"), company("B")], now=NOW), "pe_ratio")["peer_median"] is None
    assert metric(result, "free_cash_flow_yield")["peer_median"] == -.03


def test_cohort_does_not_mix_company_types_currencies_or_distant_periods():
    anchor = company("ANCHOR")
    currency, bank, old = (company(symbol) for symbol in ("EURO", "BANK", "OLD"))
    currency["info"]["currency"] = "EUR"
    bank["metrics"]["applicability_profile"]["key"] = "financial_institution"
    old["data_quality"]["analysis_basis"]["income_period_end"] = "2025-12-31"
    result = compare_peers([anchor, currency, bank, old], now=NOW)
    assert all(not row["included"] for row in result["companies"][1:])
    assert all(value is None for row in result["companies"][1:] for value in row["values"].values())


def test_industry_default_and_explicit_broader_sector_cohort():
    anchor, other = company("A"), company("B")
    other["info"]["industry"] = "Hardware"
    assert not compare_peers([anchor, other], now=NOW)["companies"][1]["included"]
    assert compare_peers([anchor, other], universe="sector", now=NOW)["companies"][1]["included"]


def test_unknown_or_stale_quotes_and_nonmeaningful_multiples_are_excluded_per_metric():
    anchor, other, negative = company("A"), company("B"), company("C", -10)
    other["data_quality"]["market_data_as_of"] = None
    result = compare_peers([anchor, other, negative], now=NOW)
    assert result["companies"][1]["values"]["pe_ratio"] is None
    assert result["companies"][1]["values"]["net_margin"] == .2
    assert result["companies"][2]["values"]["pe_ratio"] is None
    other["data_quality"]["market_data_as_of"] = "2026-10-01T00:00:00Z"
    assert compare_peers([anchor, other], now=NOW)["companies"][1]["values"]["pe_ratio"] is None


def test_cashflow_comparability_is_metric_specific_and_no_inputs_are_mutated():
    anchor, other = company("A"), company("B")
    original = deepcopy(other)
    other["data_quality"]["analysis_basis"]["cash_flow_period_end"] = "2025-12-31"
    result = compare_peers([anchor, other], now=NOW)
    assert result["companies"][1]["values"]["net_margin"] == .2
    assert result["companies"][1]["values"]["free_cash_flow_yield"] is None
    assert other["metrics"] == original["metrics"]
    with pytest.raises(ValueError):
        compare_peers([anchor, other], universe="other", now=NOW)


def test_banks_and_insurers_do_not_share_a_broader_sector_median():
    bank, insurer = company("BANK"), company("INSURER")
    for row in (bank, insurer):
        row["metrics"]["applicability_profile"]["key"] = "financial_institution"
        row["info"]["sector"] = "Financial Services"
    bank["info"]["industry"] = "Banks - Diversified"
    insurer["info"]["industry"] = "Insurance - Life"
    result = compare_peers([bank, insurer], universe="sector", now=NOW)
    assert not result["companies"][1]["included"]


def test_a_reported_full_year_remains_comparable_when_provider_ttm_is_missing():
    anchor, peer = company("A"), company("B")
    peer["data_quality"]["analysis_basis"].update(income="latest_annual_fallback", cash_flow="latest_annual_fallback")
    assert compare_peers([anchor, peer], now=NOW)["companies"][1]["included"]


def test_peer_endpoint_rejects_invalid_or_oversized_cohorts_before_provider_calls(monkeypatch):
    import main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main, "fetch_stock_data", lambda *a, **k: pytest.fail("Invalid requests must not fetch company data"))
    client = TestClient(main.app)
    for symbols in ("AAPL", "A,B,C,D,E,F", "AAPL,<script>"):
        assert client.get("/api/research/peers", params={"tickers": symbols}).status_code == 400
