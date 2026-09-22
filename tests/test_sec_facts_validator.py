import pandas as pd

import sec_facts_validator


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_latest_quarter_core_facts_match_official_values(monkeypatch):
    period = pd.Timestamp("2026-06-30")
    income = pd.DataFrame(
        {period: [100.0, 20.0]}, index=["Total Revenue", "Net Income"]
    )
    balance = pd.DataFrame(
        {period: [500.0, 200.0]}, index=["Total Assets", "Common Stock Equity"]
    )
    payload = {
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {"USD": [{"start": "2026-04-01", "end": "2026-06-29", "val": 100.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
                },
                "NetIncomeLoss": {
                    "units": {"USD": [{"start": "2026-04-01", "end": "2026-06-29", "val": 20.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
                },
                "Assets": {
                    "units": {"USD": [{"end": "2026-06-29", "val": 500.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
                },
                "StockholdersEquity": {
                    "units": {"USD": [{"end": "2026-06-29", "val": 200.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
                },
            }
        }
    }
    monkeypatch.setattr(sec_facts_validator.requests, "get", lambda *args, **kwargs: FakeResponse(payload))
    sec_facts_validator._CACHE.clear()
    result = sec_facts_validator.validate_core_sec_facts("123", income, balance, "USD")
    assert result["status"] == "matched"
    assert result["checked"] == 4
    assert result["matched"] == 4
    assert result["mismatches"] == []


def test_sec_difference_is_reported_not_silently_replaced(monkeypatch):
    period = pd.Timestamp("2026-06-30")
    income = pd.DataFrame({period: [120.0]}, index=["Total Revenue"])
    balance = pd.DataFrame({period: [500.0]}, index=["Total Assets"])
    payload = {
        "facts": {"us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {"USD": [{"start": "2026-04-01", "end": "2026-06-30", "val": 100.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
            },
            "Assets": {
                "units": {"USD": [{"end": "2026-06-30", "val": 500.0, "form": "10-Q", "filed": "2026-07-30", "accn": "x"}]}
            },
        }}
    }
    monkeypatch.setattr(sec_facts_validator.requests, "get", lambda *args, **kwargs: FakeResponse(payload))
    sec_facts_validator._CACHE.clear()
    result = sec_facts_validator.validate_core_sec_facts("124", income, balance, "USD")
    assert result["status"] == "mismatch"
    assert result["checked"] == 2
    assert result["matched"] == 1
    assert result["mismatches"][0]["metric"] == "revenue"

