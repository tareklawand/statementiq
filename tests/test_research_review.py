from copy import deepcopy

from research_review import build_research_review, input_fingerprint, methodology


def payload():
    def statement(rows, dates=("2025-12-31", "2024-12-31")):
        return {"columns": list(dates), "rows": [{"metric": key, "values": value} for key, value in rows.items()]}
    return {"symbol": "EXAMPLE", "info": {"currency": "USD"}, "data_quality": {"statement_provider": "Example source"},
            "metrics": {"applicability_profile": {"key": "operating_company"}, "raw_financials": {"revenue": 120}},
            "statements": {"income_statement": statement({"Total Revenue": [120, 100], "Net Income": [30, 20]}),
                           "cash_flow": statement({"Operating Cash Flow": [15, 25]}),
                           "balance_sheet": statement({"Accounts Receivable": [40, 20]})}}


def test_review_uses_real_aligned_periods_and_evidence_ids():
    result = build_research_review(payload())
    revenue = next(c for c in result["changes"] if c["metric"] == "revenue")
    assert revenue["absolute_change"] == 20
    assert abs(revenue["percent_change"] - .2) < 1e-10
    ids = {change["id"] for change in result["changes"]}
    assert {flag["key"] for flag in result["review_signals"]} == {"earnings_cash_divergence", "receivables_growth"}
    assert all(set(flag["evidence"]) <= ids for flag in result["review_signals"])


def test_missing_year_is_not_a_yoy_change_and_missing_zero_not_invented():
    data = payload()
    data["statements"]["income_statement"]["columns"][1] = "2023-12-31"
    assert not any(c["statement"] == "income_statement" for c in build_research_review(data)["changes"])
    data = payload()
    data["statements"]["income_statement"]["rows"][0]["values"][0] = None
    assert not any(c["metric"] == "revenue" for c in build_research_review(data)["changes"])


def test_quarterly_and_annual_are_not_mixed_and_financial_institutions_skip_operating_signals():
    data = payload()
    data["statements"]["cash_flow"]["columns"] = ["2025-09-30", "2024-09-30"]
    assert not any(f["key"] == "earnings_cash_divergence" for f in build_research_review(data)["review_signals"])
    data = payload()
    data["metrics"]["applicability_profile"]["key"] = "financial_institution"
    assert build_research_review(data)["review_signals"] == []


def test_input_digest_changes_with_inputs_not_commentary_and_methodology_is_fingerprinted():
    data = payload()
    first = input_fingerprint(data)
    copy = deepcopy(data)
    copy["ai_insights"] = {"text": "different presentation"}
    assert input_fingerprint(copy) == first
    copy["statements"]["income_statement"]["rows"][0]["values"][0] = 999
    assert input_fingerprint(copy) != first
    assert len(methodology()["code_sha256"]) == 64
    assert methodology()["independent_validation"] is False
