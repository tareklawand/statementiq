import pytest
from data_fetcher import fetch_stock_data, PRESET_TICKERS, REAL_COMPANY_PROFILES

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
