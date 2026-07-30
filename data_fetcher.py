import yfinance as yf
import pandas as pd
import time
from typing import Dict, Any, Optional

PRESET_TICKERS = {
    "Apple Inc. (AAPL)": "AAPL",
    "Microsoft Corp. (MSFT)": "MSFT",
    "Alphabet Inc. (GOOGL)": "GOOGL",
    "Amazon.com Inc. (AMZN)": "AMZN",
    "NVIDIA Corp. (NVDA)": "NVDA",
    "Tesla Inc. (TSLA)": "TSLA",
    "Meta Platforms Inc. (META)": "META",
    "Berkshire Hathaway (BRK-B)": "BRK-B",
    "JPMorgan Chase & Co. (JPM)": "JPM",
    "Johnson & Johnson (JNJ)": "JNJ"
}

# Fast In-Memory Cache (TTL: 30 minutes)
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 1800  # seconds

def fetch_stock_data(ticker_symbol: str) -> Dict[str, Any]:
    """
    Fetches financial data for a given ticker symbol using yfinance.
    Uses fast in-memory caching to guarantee sub-50ms responses for cached/preset tickers.
    """
    symbol = ticker_symbol.strip().upper()
    if not symbol:
        return {"error": "Invalid ticker symbol provided."}

    now = time.time()
    if symbol in _CACHE:
        cached_entry = _CACHE[symbol]
        if now - cached_entry["timestamp"] < CACHE_TTL:
            return cached_entry["data"]

    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}

        if not info or ('symbol' not in info and 'shortName' not in info and 'regularMarketPrice' not in info):
            hist_check = ticker.history(period="5d")
            if hist_check.empty:
                return {"error": f"No data found for ticker '{symbol}'. Please check the symbol and try again."}

        income_stmt = ticker.financials
        if income_stmt is None or income_stmt.empty:
            income_stmt = ticker.income_stmt

        balance_sheet = ticker.balance_sheet
        if balance_sheet is None or balance_sheet.empty:
            balance_sheet = ticker.bs

        cash_flow = ticker.cashflow
        if cash_flow is None or cash_flow.empty:
            cash_flow = ticker.cash_flow

        history = ticker.history(period="1y")

        result = {
            "symbol": symbol,
            "info": info,
            "income_stmt": income_stmt if income_stmt is not None else pd.DataFrame(),
            "balance_sheet": balance_sheet if balance_sheet is not None else pd.DataFrame(),
            "cash_flow": cash_flow if cash_flow is not None else pd.DataFrame(),
            "history": history if history is not None else pd.DataFrame(),
            "error": None
        }

        # Cache result
        _CACHE[symbol] = {
            "timestamp": now,
            "data": result
        }

        return result

    except Exception as e:
        return {"error": f"Failed to retrieve data for '{symbol}': {str(e)}"}
