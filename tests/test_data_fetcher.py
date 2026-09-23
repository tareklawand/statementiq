import pytest
import pandas as pd
import data_fetcher
from data_fetcher import fetch_stock_data, PRESET_TICKERS

def test_fetch_preset_tickers():
    for label, symbol in PRESET_TICKERS.items():
        data = fetch_stock_data(symbol)
        assert data["symbol"] == symbol
        assert "info" in data
        assert "income_stmt" in data
        assert "balance_sheet" in data
        assert "cash_flow" in data

def test_financial_sector_flag():
    jpm_data = fetch_stock_data("JPM")
    assert jpm_data["is_financial_sector"] is True
    
    brk_data = fetch_stock_data("BRK-B")
    assert brk_data["is_financial_sector"] is True

    aapl_data = fetch_stock_data("AAPL")
    assert aapl_data["is_financial_sector"] is False

def test_unmapped_ticker_missing_data():
    data = fetch_stock_data("NON_EXISTENT_TICKER_99")
    assert data["symbol"] == "NON_EXISTENT_TICKER_99"
    assert data["error"] is not None


def test_live_failure_never_uses_static_profile(monkeypatch):
    class BrokenTicker:
        def __init__(self, symbol):
            raise RuntimeError("provider unavailable")

    data_fetcher._CACHE.pop("AAPL", None)
    monkeypatch.setattr(data_fetcher.yf, "Ticker", BrokenTicker)
    data = fetch_stock_data("AAPL")

    assert data["error"] is not None
    assert data["info"]["data_source"] == "unavailable"
    assert data["income_stmt"].empty
    assert data["balance_sheet"].empty


def test_non_company_security_is_rejected_instead_of_forcing_company_ratios(monkeypatch):
    class FundTicker:
        def __init__(self, symbol):
            self.info = {"symbol": symbol, "quoteType": "ETF"}

    monkeypatch.setattr(data_fetcher.yf, "Ticker", FundTicker)
    data = fetch_stock_data("SPY", force_refresh=True)
    assert data["error"] is not None
    assert "not a public-company equity" in data["error"]


def test_live_market_fallbacks_recover_when_quote_summary_is_empty():
    dates = pd.to_datetime(["2026-09-21", "2026-09-22"], utc=True)

    class FallbackTicker:
        fast_info = {
            "lastPrice": 229.17,
            "regularMarketPreviousClose": 227.38,
            "marketCap": 5_533_767_565_312,
            "shares": 24_147_000_000,
            "currency": "USD",
            "exchange": "NMS",
            "quoteType": "EQUITY",
            "yearHigh": 236.54,
            "yearLow": 164.27,
        }
        analyst_price_targets = {"mean": 327.70}

        def history(self, **kwargs):
            return pd.DataFrame(
                {
                    "Close": [227.38, 229.17],
                    "High": [230.00, 231.00],
                    "Low": [224.00, 225.00],
                    "Dividends": [0.01, 0.01],
                },
                index=dates,
            )

        def get_history_metadata(self):
            return {
                "regularMarketTime": 1_790_098_651,
                "currency": "USD",
                "exchangeName": "NMS",
                "instrumentType": "EQUITY",
            }

    info = data_fetcher._enrich_info_with_live_market_fallbacks(FallbackTicker(), {})

    assert info["regularMarketPrice"] == 229.17
    assert info["previousClose"] == 227.38
    assert info["marketCap"] == 5_533_767_565_312
    assert info["sharesOutstanding"] == 24_147_000_000
    assert info["fiftyTwoWeekHigh"] == 236.54
    assert info["fiftyTwoWeekLow"] == 164.27
    assert info["targetMeanPrice"] == 327.70
    assert info["dividendRate"] == pytest.approx(0.02)
    assert info["dividendRateBasis"] == "trailing_twelve_months_cash_dividends"
    assert info["market_data_route"] == "quote_summary+live_fallbacks"


def test_live_market_fallbacks_do_not_overwrite_primary_provider_values():
    class PrimaryTicker:
        fast_info = {"lastPrice": 999.0, "marketCap": 999_000.0}
        analyst_price_targets = {"mean": 999.0}

        def history(self, **kwargs):
            return pd.DataFrame()

        def get_history_metadata(self):
            return {}

    original = {
        "regularMarketPrice": 100.0,
        "marketCap": 1_000.0,
        "targetMeanPrice": 120.0,
        "dividendRate": 1.0,
    }
    info = data_fetcher._enrich_info_with_live_market_fallbacks(PrimaryTicker(), original)

    assert info["regularMarketPrice"] == 100.0
    assert info["marketCap"] == 1_000.0
    assert info["targetMeanPrice"] == 120.0
    assert info["dividendRate"] == 1.0
    assert info["dividendRateBasis"] == "provider_forward_annual_rate"
