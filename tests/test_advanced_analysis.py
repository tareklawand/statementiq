import pandas as pd
import pytest

from metrics_calculator import compute_metrics
from sec_filing_validator import _filing_signals
import sec_filing_validator
from statement_analysis import prepare_statement_analysis
from filing_disclosure_analyzer import analyze_filing_text
import filing_disclosure_analyzer


def complete_company_fixture():
    latest = pd.Timestamp("2025-12-31")
    prior = pd.Timestamp("2024-12-31")
    income = pd.DataFrame(
        {
            latest: [1000.0, 600.0, 400.0, 200.0, 180.0, 36.0, 144.0, 100.0, 2.0, 100.0],
            prior: [900.0, 540.0, 360.0, 170.0, 150.0, 30.0, 120.0, 90.0, 1.6, 100.0],
        },
        index=[
            "Total Revenue", "Cost Of Revenue", "Gross Profit", "Operating Income",
            "Pretax Income", "Tax Provision", "Net Income", "Research And Development",
            "Diluted EPS", "Diluted Average Shares",
        ],
    )
    balance = pd.DataFrame(
        {
            latest: [1000.0, 100.0, 120.0, 80.0, 90.0, 300.0, 500.0, 400.0, 250.0, 100.0],
            prior: [900.0, 80.0, 100.0, 70.0, 80.0, 280.0, 450.0, 360.0, 230.0, 100.0],
        },
        index=[
            "Total Assets", "Cash And Cash Equivalents", "Receivables", "Inventory",
            "Accounts Payable", "Total Debt", "Stockholders Equity", "Current Assets",
            "Current Liabilities", "Ordinary Shares Number",
        ],
    )
    cash_flow = pd.DataFrame(
        {
            latest: [180.0, -40.0, 140.0, 20.0, -30.0, -50.0, 10.0, 20.0],
            prior: [140.0, -40.0, 100.0, 18.0, -25.0, -35.0, 8.0, 18.0],
        },
        index=[
            "Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
            "Stock Based Compensation", "Cash Dividends Paid", "Repurchase Of Capital Stock",
            "Issuance Of Capital Stock", "Depreciation And Amortization",
        ],
    )
    return {
        "symbol": "TEST",
        "info": {
            "symbol": "TEST", "sector": "Industrials", "industry": "Specialty Industrial Machinery",
            "regularMarketPrice": 50.0, "marketCap": 5000.0, "sharesOutstanding": 100.0,
            "epsTrailingTwelveMonths": 2.0, "currency": "USD", "financialCurrency": "USD",
        },
        "income_stmt": income,
        "balance_sheet": balance,
        "cash_flow": cash_flow,
        "analysis_basis": {"income": "latest_annual", "balance_sheet": "latest_annual"},
    }


def test_advanced_metrics_use_reported_inputs_and_exact_formulas():
    result = compute_metrics(complete_company_fixture())
    advanced = result["advanced_metrics"]

    assert advanced["effective_tax_rate"] == pytest.approx(0.20)
    assert advanced["nopat"] == pytest.approx(160.0)
    assert advanced["roic"] == pytest.approx(160.0 / 675.0)
    assert advanced["dso"] == pytest.approx(365.0 * 110.0 / 1000.0)
    assert advanced["dio"] == pytest.approx(365.0 * 75.0 / 600.0)
    assert advanced["dpo"] == pytest.approx(365.0 * 85.0 / 600.0)
    assert advanced["cash_conversion_cycle"] == pytest.approx(
        advanced["dso"] + advanced["dio"] - advanced["dpo"]
    )
    assert advanced["accrual_ratio"] == pytest.approx((144.0 - 180.0) / 950.0)
    assert advanced["operating_cash_flow_margin"] == pytest.approx(0.18)
    assert advanced["capex_to_revenue"] == pytest.approx(0.04)
    assert advanced["stock_comp_to_revenue"] == pytest.approx(0.02)
    assert advanced["stock_comp_to_fcf"] == pytest.approx(20.0 / 140.0)
    assert advanced["price_to_sales"] == pytest.approx(5.0)
    assert advanced["price_to_book"] == pytest.approx(10.0)
    assert advanced["ev_to_sales"] == pytest.approx(5.2)
    assert advanced["earnings_yield"] == pytest.approx(144.0 / 5000.0)
    assert advanced["dividend_yield_cash_flow"] == pytest.approx(30.0 / 5000.0)
    assert advanced["net_buyback_yield"] == pytest.approx(40.0 / 5000.0)
    assert advanced["shareholder_yield"] == pytest.approx(70.0 / 5000.0)
    assert advanced["revenue_per_share"] == pytest.approx(10.0)
    assert advanced["free_cash_flow_per_share"] == pytest.approx(1.4)
    assert advanced["book_value_per_share"] == pytest.approx(5.0)
    assert advanced["annual_eps_growth"] == pytest.approx(0.25)
    assert advanced["annual_fcf_growth"] == pytest.approx(0.40)
    assert advanced["revenue_per_share_growth"] == pytest.approx(1000.0 / 900.0 - 1.0)


def test_advanced_metrics_never_replace_missing_inputs_with_zero():
    fixture = complete_company_fixture()
    fixture["balance_sheet"] = fixture["balance_sheet"].drop(index="Accounts Payable")
    result = compute_metrics(fixture)["advanced_metrics"]
    assert result["dpo"] is None
    assert result["cash_conversion_cycle"] is None


def test_financial_institution_suppresses_industrial_advanced_metrics():
    fixture = complete_company_fixture()
    fixture["symbol"] = "JPM"
    fixture["info"].update({"symbol": "JPM", "sector": "Financial Services", "industry": "Banks - Diversified"})
    advanced = compute_metrics(fixture)["advanced_metrics"]
    assert advanced["roic"] is None
    assert advanced["cash_conversion_cycle"] is None
    assert advanced["operating_cash_flow_margin"] is None
    assert advanced["ev_to_sales"] is None


def test_statement_analysis_common_size_and_change_are_deterministic():
    fixture = complete_company_fixture()
    analysis = prepare_statement_analysis(
        fixture["income_stmt"], fixture["balance_sheet"], fixture["cash_flow"], fixture["income_stmt"]
    )
    income_rows = {row["metric"]: row for row in analysis["annual"]["income_statement"]["rows"]}
    balance_rows = {row["metric"]: row for row in analysis["annual"]["balance_sheet"]["rows"]}
    assert income_rows["Gross profit"]["common_size"][0] == pytest.approx(0.40)
    assert income_rows["Revenue"]["period_over_period_change"][0] == pytest.approx(1000.0 / 900.0 - 1.0)
    assert balance_rows["Total debt"]["common_size"][0] == pytest.approx(0.30)
    assert analysis["methodology"]["missing_value_policy"].startswith("Missing")


def test_sec_signals_use_official_form_and_item_codes():
    recent = {
        "form": ["8-K", "8-K", "10-Q/A", "10-Q"],
        "items": ["4.02", "4.01", "", ""],
        "filingDate": ["2026-02-01", "2025-07-01", "2025-05-01", "2025-04-01"],
        "reportDate": ["2026-01-31", "2025-06-30", "2025-03-31", "2025-03-31"],
        "accessionNumber": ["1-1", "1-2", "1-3", "1-4"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"],
    }
    signals = _filing_signals(recent, "0000320193")
    assert [signal["type"] for signal in signals] == [
        "non_reliance_restatement", "auditor_change", "amended_periodic_filing"
    ]
    assert signals[0]["filing_url"].startswith("https://www.sec.gov/Archives/edgar/data/")


def test_filing_phrase_review_locates_topics_without_making_risk_conclusions():
    result = analyze_filing_text("""
        <html><body><h2>Critical Audit Matters</h2>
        <p>Management identified a material weakness in internal control.</p>
        <p>See the notes on operating leases and revenue recognition.</p></body></html>
    """)
    topics = {topic["key"]: topic for topic in result["topics"]}
    assert topics["material_weakness"]["status"] == "located"
    assert topics["critical_audit_matter"]["status"] == "located"
    assert topics["leases"]["status"] == "located"
    assert topics["revenue_recognition"]["status"] == "located"
    assert topics["going_concern"]["status"] == "not_located_by_phrase_scan"
    assert "not a conclusion" in result["scope"]


def test_filing_review_uses_locked_edge_fallback_after_sec_rate_limit(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, text=""):
            self.status_code = status_code
            self.text = text
            self.content = text.encode()

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status {self.status_code}")

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(403)
        return FakeResponse(200, "<html><body>Critical audit matter</body></html>")

    filing_disclosure_analyzer._CACHE.clear()
    monkeypatch.setattr(filing_disclosure_analyzer.requests, "get", fake_get)
    result = filing_disclosure_analyzer.scan_annual_filing(
        "https://www.sec.gov/Archives/edgar/data/1/example.htm"
    )
    assert result["status"] == "analyzed"
    assert calls[1].startswith("https://statementiq-lb.com/api/sec-filing-text?")


def test_full_submission_scan_ignores_exhibit_language():
    submission = """
        <DOCUMENT><TYPE>10-K\n<TEXT><html><body>Critical audit matter and operating leases.</body></html></TEXT></DOCUMENT>
        <DOCUMENT><TYPE>EX-99\n<TEXT><html><body>Management identified a material weakness.</body></html></TEXT></DOCUMENT>
    """
    result = analyze_filing_text(submission)
    topics = {topic["key"]: topic for topic in result["topics"]}
    assert topics["critical_audit_matter"]["status"] == "located"
    assert topics["leases"]["status"] == "located"
    assert topics["material_weakness"]["status"] == "not_located_by_phrase_scan"


def test_sec_ticker_directory_uses_fixed_edge_fallback(monkeypatch):
    calls = []

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"status {self.status_code}")

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return FakeResponse(403)
        return FakeResponse(200, {"0": {"ticker": "XOM", "cik_str": 34088, "title": "EXXON MOBIL CORP"}})

    monkeypatch.setattr(sec_filing_validator, "_TICKER_MAP", {})
    monkeypatch.setattr(sec_filing_validator, "_TICKER_MAP_FETCHED_AT", 0.0)
    monkeypatch.setattr(sec_filing_validator.requests, "get", fake_get)
    mapped = sec_filing_validator._load_ticker_map()
    assert mapped["XOM"]["cik"] == "0000034088"
    assert calls[1] == "https://statementiq-lb.com/api/sec-ticker-map"
