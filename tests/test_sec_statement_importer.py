"""Synthetic accounting examples, never production financial snapshots."""
from copy import deepcopy
from datetime import date, timedelta

import pandas as pd
import pytest

import data_fetcher
import sec_filing_validator
import sec_statement_importer as importer
from metrics_calculator import compute_metrics


def fixture():
    payload = {"cik": 123456, "facts": {"us-gaap": {}}}
    def add(tag, value, start, end, accession, form="10-K", unit="USD", filed="2026-02-01"):
        entry = {"end": end, "val": value, "accn": accession, "form": form, "filed": filed}
        if start is not None:
            entry["start"] = start
        payload["facts"]["us-gaap"].setdefault(tag, {"units": {}})["units"].setdefault(unit, []).append(entry)
    for year, accession in [(2024, "annual-2024"), (2025, "annual-2025")]:
        start, end = f"{year}-01-01", f"{year}-12-31"
        for tag, value in {
            "Revenues": 1000 if year == 2025 else 800, "NetIncomeLoss": 100,
            "CostOfRevenue": 600, "OperatingIncomeLoss": 200,
            "NetCashProvidedByUsedInOperatingActivities": 180, "PaymentsToAcquirePropertyPlantAndEquipment": 30,
            "DepreciationDepletionAndAmortization": 20, "ShareBasedCompensation": 10,
        }.items():
            add(tag, value, start, end, accession)
        for tag, value in {
            "Assets": 900, "LiabilitiesAndStockholdersEquity": 900,
            "StockholdersEquity": 500, "AssetsCurrent": 400, "LiabilitiesCurrent": 200,
            "CashAndCashEquivalentsAtCarryingValue": 100, "ShortTermInvestments": 10,
            "AccountsReceivableNetCurrent": 80, "DebtCurrent": 50, "LongTermDebtNoncurrent": 100,
        }.items():
            add(tag, value, None, end, accession)
        add("EarningsPerShareDiluted", 2, start, end, accession, unit="USD/shares")
        add("WeightedAverageNumberOfDilutedSharesOutstanding", 50, start, end, accession, unit="shares")
    filing = {"status": "verified", "cik": "0000123456", "form": "10-K", "report_period": "2025-12-31",
              "accession_number": "annual-2025", "filed_date": "2026-02-01"}
    return payload, filing, add


def quarterly_fixture():
    payload, filing, add = fixture()
    filing.update(form="10-Q", report_period="2026-06-30", accession_number="quarter-2026")
    for year, total, ocf in [(2025, 400, 70), (2026, 550, 110)]:
        accession = "quarter-2026"  # current filing includes prior-YTD comparative
        for tag, value in {"Revenues": total, "NetIncomeLoss": total / 10,
                           "NetCashProvidedByUsedInOperatingActivities": ocf,
                           "PaymentsToAcquirePropertyPlantAndEquipment": 15}.items():
            add(tag, value, f"{year}-01-01", f"{year}-06-30", accession, form="10-Q", filed="2026-08-01")
        # First-quarter CF is cumulative; Q2 must be six months minus Q1.
        for tag, value in {"Revenues": total / 2, "NetIncomeLoss": total / 20,
                           "NetCashProvidedByUsedInOperatingActivities": 30,
                           "PaymentsToAcquirePropertyPlantAndEquipment": 5}.items():
            add(tag, value, f"{year}-01-01", f"{year}-03-31", f"q1-{year}", form="10-Q", filed="2026-05-01")
    for end, accession in [("2026-06-30", "quarter-2026"), ("2025-06-30", "quarter-2026")]:
        for tag, value in {"Assets": 1000, "LiabilitiesAndStockholdersEquity": 1000,
                           "StockholdersEquity": 550, "DebtCurrent": 50, "LongTermDebtNoncurrent": 100}.items():
            add(tag, value, None, end, accession, form="10-Q", filed="2026-08-01")
    add("EarningsPerShareDiluted", 9.99, "2026-01-01", "2026-06-30", "quarter-2026", form="10-Q", unit="USD/shares")
    return payload, filing, add


def test_annual_import_has_exact_reported_values_and_source_provenance():
    payload, filing, _ = fixture()
    result = importer.build_sec_statements(payload, filing)
    assert result["basis"] == "latest_annual"
    assert result["frames"]["analysis_income_stmt"].iloc[0, 0] == 1000
    assert result["frames"]["analysis_cash_flow"].loc["Free Cash Flow"].iloc[0] == 150
    assert result["frames"]["analysis_cash_flow"].loc["Capital Expenditure"].iloc[0] == -30
    assert result["integrity_checks"][0]["matched"]
    cell = result["provenance"]["annual_income:2025-12-31"]["Total Revenue"]
    assert cell["sources"][0]["accession_number"] == "annual-2025"
    assert cell["sources"][0]["unit"] == "USD"
    assert cell["sources"][0]["tag"] == "Revenues"


def test_ytd_is_not_mistaken_for_quarter_and_ttm_is_not_annualized():
    payload, filing, _ = quarterly_fixture()
    result = importer.build_sec_statements(payload, filing)
    frames = result["frames"]
    assert frames["quarterly_cash_flow"].loc["Operating Cash Flow"].iloc[0] == 80  # 110 - 30
    assert frames["analysis_income_stmt"].loc["Total Revenue"].iloc[0] == 1150  # 1000 + 550 - 400
    assert frames["analysis_cash_flow"].loc["Operating Cash Flow"].iloc[0] == 220  # 180 + 110 - 70
    assert frames["analysis_cash_flow"].loc["Free Cash Flow"].iloc[0] == 190
    for cells in result["provenance"].values():
        for cell in cells.values():
            assert cell["value"] == pytest.approx(sum(source["value"] * source["coefficient"] for source in cell["sources"]))
    assert "Diluted EPS" not in frames["analysis_income_stmt"].index
    assert "Diluted Average Shares" not in frames["analysis_income_stmt"].index


def test_incomplete_latest_accession_never_reuses_old_same_period_values():
    payload, filing, add = fixture()
    filing["accession_number"] = "amended-but-incomplete"
    filing["form"] = "10-K/A"
    add("NetIncomeLoss", 90, "2025-01-01", "2025-12-31", "amended-but-incomplete", form="10-K/A")
    with pytest.raises(importer.ImportUnavailable, match="core dataset"):
        importer.build_sec_statements(payload, filing)


def test_missing_optional_rows_are_not_replaced_with_zero():
    payload, filing, _ = fixture()
    del payload["facts"]["us-gaap"]["PaymentsToAcquirePropertyPlantAndEquipment"]
    result = importer.build_sec_statements(payload, filing)
    cash = result["frames"]["analysis_cash_flow"]
    assert "Capital Expenditure" not in cash.index
    assert "Free Cash Flow" not in cash.index


def test_balance_mismatch_prevents_import():
    payload, filing, _ = fixture()
    payload["facts"]["us-gaap"]["Assets"]["units"]["USD"][-1]["val"] = 999
    with pytest.raises(importer.ImportUnavailable, match="reconciliation failed"):
        importer.build_sec_statements(payload, filing)


def test_wrong_registrant_and_unsupported_taxonomy_are_rejected():
    payload, filing, _ = fixture()
    with pytest.raises(importer.ImportUnavailable, match="registrant"):
        importer.build_sec_statements({**payload, "cik": 999999}, filing)
    payload["facts"] = {"ifrs-full": payload["facts"]["us-gaap"]}
    with pytest.raises(importer.ImportUnavailable, match="supported"):
        importer.build_sec_statements(payload, filing)


def test_income_reconciliation_prevents_mismatched_concepts():
    payload, filing, add = fixture()
    add("GrossProfit", 123, "2025-01-01", "2025-12-31", "annual-2025")
    with pytest.raises(importer.ImportUnavailable, match="income-statement reconciliation"):
        importer.build_sec_statements(payload, filing)


def test_conflicting_duplicate_core_facts_prevent_import():
    payload, filing, add = fixture()
    add("Revenues", 9999, "2025-01-01", "2025-12-31", "annual-2025")
    with pytest.raises(importer.ImportUnavailable, match="Conflicting SEC values"):
        importer.build_sec_statements(payload, filing)


def test_units_are_never_mixed_and_ambiguous_currency_is_rejected():
    payload, filing, _ = fixture()
    payload["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["EUR"] = deepcopy(payload["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"])
    with pytest.raises(importer.ImportUnavailable, match="currency"):
        importer.build_sec_statements(payload, filing)
    assert importer.build_sec_statements(payload, filing, "USD")["currency"] == "USD"


def test_no_short_term_debt_is_not_inferred_from_absence():
    payload, filing, _ = fixture()
    del payload["facts"]["us-gaap"]["DebtCurrent"]
    result = importer.build_sec_statements(payload, filing)
    assert "Total Debt" not in result["frames"]["analysis_balance_sheet"].index


def test_restated_comparative_wins_and_non_periodic_facts_are_ignored():
    payload, filing, add = fixture()
    add("Revenues", 850, "2024-01-01", "2024-12-31", "annual-2025", filed="2026-02-02")
    add("Revenues", 9999, "2025-01-01", "2025-12-31", "proxy", form="DEF 14A", filed="2026-03-01")
    result = importer.build_sec_statements(payload, filing)
    assert result["frames"]["income_stmt"].loc["Total Revenue"].tolist() == [1000, 850]


def test_next_filing_changes_values_without_any_ticker_specific_code():
    payload, filing, _ = fixture()
    old_filing = {**filing, "report_period": "2024-12-31", "accession_number": "annual-2024"}
    first = importer.build_sec_statements(payload, old_filing)
    second = importer.build_sec_statements(payload, filing)
    assert first["frames"]["analysis_income_stmt"].loc["Total Revenue"].iloc[0] == 800
    assert second["frames"]["analysis_income_stmt"].loc["Total Revenue"].iloc[0] == 1000
    assert second["report_period"] == "2025-12-31"


def test_future_period_is_rejected():
    payload, filing, _ = fixture()
    next_filing = {**filing, "report_period": (date.today() + timedelta(days=400)).isoformat()}
    with pytest.raises(importer.ImportUnavailable, match="future"):
        importer.build_sec_statements(payload, next_filing)


def test_company_facts_cache_is_invalidated_by_new_accession(monkeypatch):
    payload, _, _ = fixture()
    class Response:
        def raise_for_status(self): pass
        def json(self): return payload
    calls = []
    monkeypatch.setattr(importer.requests, "get", lambda *a, **k: calls.append(a[0]) or Response())
    monkeypatch.setattr(importer.time, "sleep", lambda n: None)
    importer._CACHE.clear()
    importer.get_company_facts("123456", "a")
    importer.get_company_facts("123456", "a")
    importer.get_company_facts("123456", "b")
    assert len(calls) == 2


def test_sec_inputs_replace_old_provider_frames_for_an_unlisted_company(monkeypatch):
    payload, filing, _ = fixture()
    filing.update(sic="7372", sic_description="Services-Prepackaged Software", registrant="Example company")
    class Ticker:
        info = {"currency": "USD", "regularMarketPrice": 50, "epsTrailingTwelveMonths": 99}
        sec_filings = []
    monkeypatch.setattr(data_fetcher.yf, "Ticker", lambda symbol: Ticker())
    monkeypatch.setattr(data_fetcher, "_enrich_info_with_live_market_fallbacks", lambda t, info: dict(info))
    monkeypatch.setattr(data_fetcher, "get_latest_sec_filing", lambda *a, **k: filing)
    monkeypatch.setattr(importer, "get_company_facts", lambda *a: payload)
    result = data_fetcher.fetch_stock_data("NOT_IN_PRESETS", force_refresh=True)
    assert result["error"] is None
    assert result["info"]["statement_data_provider"] == "SEC Company Facts"
    assert result["analysis_basis"]["income_period_end"] == "2025-12-31"
    assert result["integrity_hold_reason"] is None
    metrics = compute_metrics(result)
    assert metrics["ratios"]["pe_ratio"] == 25  # statement EPS 2, not Yahoo's stale 99
    assert result["info"]["classification_source"] == "SEC SIC"


def test_failed_import_keeps_recency_hold_instead_of_publishing_old_score(monkeypatch):
    _, filing, _ = fixture()
    class Ticker:
        info = {"sector": "Technology", "industry": "Software", "financialCurrency": "USD"}
        sec_filings = []
        income_stmt = pd.DataFrame({pd.Timestamp("2024-12-31"): [800]}, index=["Total Revenue"])
        balance_sheet = pd.DataFrame({pd.Timestamp("2024-12-31"): [900]}, index=["Total Assets"])
    monkeypatch.setattr(data_fetcher.yf, "Ticker", lambda s: Ticker())
    monkeypatch.setattr(data_fetcher, "_enrich_info_with_live_market_fallbacks", lambda t, i: dict(i))
    monkeypatch.setattr(data_fetcher, "get_latest_sec_filing", lambda *a, **k: filing)
    monkeypatch.setattr(data_fetcher, "import_latest_sec_statements", lambda *a: {"status": "unavailable", "reason": "XBRL not ready"})
    monkeypatch.setattr(data_fetcher, "validate_core_sec_facts", lambda *a: {"status": "unavailable"})
    data = data_fetcher.fetch_stock_data("WAITING", force_refresh=True)
    assert data["provider_lags_latest_filing"] is True
    assert "newest SEC filing" in data["integrity_hold_reason"]
    assert compute_metrics(data)["health_score"] is None


def test_refresh_bypasses_filing_metadata_cache(monkeypatch):
    old = {"status": "verified", "report_period": "2024-12-31"}
    sec_filing_validator._FILING_CACHE["REFRESH"] = {"timestamp": sec_filing_validator.time.time(), "data": old}
    calls = []
    class Response:
        def raise_for_status(self): pass
        def json(self): return {"name": "Example", "filings": {"recent": {
            "form": ["10-K"], "reportDate": ["2025-12-31"], "filingDate": ["2026-02-01"],
            "accessionNumber": ["new"], "primaryDocument": ["filing.htm"],
        }}}
    monkeypatch.setattr(sec_filing_validator.requests, "get", lambda *a, **k: calls.append(a[0]) or Response())
    result = sec_filing_validator.get_latest_sec_filing("REFRESH", "123456", force_refresh=True)
    assert result["report_period"] == "2025-12-31"
    assert len(calls) == 1


def test_newer_annual_statement_beats_an_older_ttm_response():
    annual = pd.DataFrame({pd.Timestamp("2025-12-31"): [1000]}, index=["Total Revenue"])
    ttm = pd.DataFrame({pd.Timestamp("2025-09-30"): [900]}, index=["Total Revenue"])
    chosen, basis = data_fetcher._select_flow_statement(ttm, annual)
    assert chosen.iloc[0, 0] == 1000
    assert basis == "latest_annual_fallback"


def test_current_provider_dataset_is_preserved_not_replaced_by_a_sparser_import(monkeypatch):
    _, filing, _ = fixture()
    class Ticker:
        info = {"sector": "Technology", "industry": "Software", "financialCurrency": "USD"}
        sec_filings = []
        income_stmt = pd.DataFrame({pd.Timestamp("2025-12-31"): [1000]}, index=["Total Revenue"])
        balance_sheet = pd.DataFrame({pd.Timestamp("2025-12-31"): [900]}, index=["Total Assets"])
        cashflow = pd.DataFrame({pd.Timestamp("2025-12-31"): [180]}, index=["Operating Cash Flow"])
    monkeypatch.setattr(data_fetcher.yf, "Ticker", lambda s: Ticker())
    monkeypatch.setattr(data_fetcher, "_enrich_info_with_live_market_fallbacks", lambda t, i: dict(i))
    monkeypatch.setattr(data_fetcher, "get_latest_sec_filing", lambda *a, **k: filing)
    def must_not_import(*args):
        raise AssertionError("Current statements must not be degraded")
    monkeypatch.setattr(data_fetcher, "import_latest_sec_statements", must_not_import)
    monkeypatch.setattr(data_fetcher, "validate_core_sec_facts", lambda *a: {"status": "unavailable"})
    data = data_fetcher.fetch_stock_data("CURRENT", force_refresh=True)
    assert data["error"] is None
    assert data["sec_statement_import"]["status"] == "not_needed"
    assert data["info"]["statement_data_provider"] == "Yahoo Finance"
    assert data["integrity_hold_reason"] is None


def test_year_ago_balance_is_selected_by_date_even_with_missing_quarters():
    dates = pd.to_datetime(["2025-12-31", "2025-06-30", "2024-12-31"])
    data = {"info": {"sector": "Technology"},
            "analysis_income_stmt": pd.DataFrame({dates[0]: [100]}, index=["Net Income"]),
            "analysis_balance_sheet": pd.DataFrame({dates[0]: [1000], dates[1]: [900], dates[2]: [800]}, index=["Total Assets"]),
            "analysis_basis": {"balance_sheet": "latest_quarter"}}
    assert compute_metrics(data)["ratios"]["roa"] == pytest.approx(100 / 900)


def test_missing_prior_year_is_not_treated_as_one_year_of_growth():
    frame = pd.DataFrame({pd.Timestamp("2025-12-31"): [1000], pd.Timestamp("2023-12-31"): [500]}, index=["Total Revenue"])
    result = compute_metrics({"info": {"sector": "Technology"}, "income_stmt": frame})
    assert result["supplemental_metrics"]["annual_revenue_growth"] is None
