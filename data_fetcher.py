import streamlit as st
import yfinance as yf
import pandas as pd
from typing import Dict, Any, Tuple, Optional

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

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_stock_data(ticker_symbol: str) -> Dict[str, Any]:
    """
    Fetches financial data for a given ticker symbol using yfinance.
    Returns a dictionary containing ticker info, financial statements, and price history.
    """
    symbol = ticker_symbol.strip().upper()
    if not symbol:
        return {"error": "Invalid ticker symbol provided."}
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Info dictionary
        info = ticker.info or {}
        
        # Check if valid ticker returned info (or shortName/longName)
        if not info or ('symbol' not in info and 'shortName' not in info and 'regularMarketPrice' not in info):
            # Try fetching fast_info or history as backup check
            hist_check = ticker.history(period="5d")
            if hist_check.empty:
                return {"error": f"No data found for ticker '{symbol}'. Please check the symbol and try again."}

        # Financial Statements (Annual)
        income_stmt = ticker.financials
        if income_stmt is None or income_stmt.empty:
            income_stmt = ticker.income_stmt

        balance_sheet = ticker.balance_sheet
        if balance_sheet is None or balance_sheet.empty:
            balance_sheet = ticker.bs

        cash_flow = ticker.cashflow
        if cash_flow is None or cash_flow.empty:
            cash_flow = ticker.cash_flow

        # Price History for charts (e.g. 1 year)
        history = ticker.history(period="1y")

        return {
            "symbol": symbol,
            "info": info,
            "income_stmt": income_stmt if income_stmt is not None else pd.DataFrame(),
            "balance_sheet": balance_sheet if balance_sheet is not None else pd.DataFrame(),
            "cash_flow": cash_flow if cash_flow is not None else pd.DataFrame(),
            "history": history if history is not None else pd.DataFrame(),
            "error": None
        }

    except Exception as e:
        return {"error": f"Failed to retrieve data for '{symbol}': {str(e)}"}
