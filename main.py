import os
import json
import io
import sys
import threading
import pandas as pd
import numpy as np

sys.path.append('/Users/tareklawand/Library/Python/3.9/lib/python/site-packages')

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any

from data_fetcher import fetch_stock_data, PRESET_TICKERS
from metrics_calculator import compute_metrics
from ai_analyst import generate_ai_insights
from pdf_generator import generate_pdf_report

app = FastAPI(title="StatementIQ Financial API")

# Mount static files directory
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

def prewarm_cache():
    """Background task to pre-fetch preset bluechip tickers on startup."""
    print("⚡ Pre-warming financial data cache for preset tickers...")
    for label, symbol in PRESET_TICKERS.items():
        try:
            fetch_stock_data(symbol)
        except Exception:
            pass
    print("✅ Pre-warming complete!")

@app.on_event("startup")
def startup_event():
    threading.Thread(target=prewarm_cache, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serves the main custom web application frontend with cache-busting headers."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            headers = {"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
            return HTMLResponse(content=f.read(), headers=headers)
    return "<h1>StatementIQ UI loading...</h1>"

@app.get("/api/presets")
def get_presets():
    """Returns preset tickers list."""
    return {"presets": PRESET_TICKERS}

@app.get("/api/analyze")
def analyze_ticker(ticker: str = Query(..., description="Stock Ticker Symbol"), api_key: Optional[str] = Query(None)):
    """
    Fetches financial data, computes 10 ratios, health score, chart data, and AI insights.
    """
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")

    stock_data = fetch_stock_data(symbol)
    if stock_data.get("error"):
        raise HTTPException(status_code=400, detail=stock_data["error"])

    info = stock_data.get("info", {})
    metrics = compute_metrics(stock_data)

    company_name = info.get("longName") or info.get("shortName") or symbol

    ai_insights = generate_ai_insights(
        company_name=company_name,
        symbol=symbol,
        health_score=metrics["health_score"],
        ratios_summary=metrics["ratio_evaluations"],
        api_key=api_key
    )

    income_stmt = stock_data.get("income_stmt", pd.DataFrame())
    balance_sheet = stock_data.get("balance_sheet", pd.DataFrame())
    
    charts_data = prepare_charts_data(income_stmt, balance_sheet)
    statements_data = prepare_statements_data(income_stmt, balance_sheet, stock_data.get("cash_flow", pd.DataFrame()))

    return {
        "symbol": symbol,
        "company_name": company_name,
        "info": {
            "sector": info.get("sector", "General Industry"),
            "industry": info.get("industry", "General Business"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", "US NASDAQ/NYSE"),
            "price": info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "fifty_two_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": info.get("dividendYield"),
            "target_price": info.get("targetMeanPrice"),
        },
        "metrics": metrics,
        "ai_insights": ai_insights,
        "charts": charts_data,
        "statements": statements_data
    }

class PDFRequest(BaseModel):
    symbol: str
    company_name: str
    metrics: Dict[str, Any]
    ai_insights: Dict[str, Any]

@app.post("/api/download-pdf")
def download_pdf(payload: PDFRequest):
    """Generates and streams downloadable ReportLab PDF report."""
    try:
        pdf_buf = generate_pdf_report(
            company_name=payload.company_name,
            symbol=payload.symbol,
            metrics=payload.metrics,
            ai_insights=payload.ai_insights
        )
        return StreamingResponse(
            pdf_buf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={payload.symbol}_Financial_Audit_Report.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def prepare_charts_data(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame) -> Dict[str, Any]:
    """Helper to extract clean series arrays for frontend charts."""
    rev_chart = {"years": [], "revenue": [], "net_income": [], "gross_margin": [], "net_margin": []}
    cash_debt_chart = {"years": [], "cash": [], "debt": []}

    if income_stmt is not None and not income_stmt.empty:
        cols = list(income_stmt.columns)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]
        rev_chart["years"] = years

        index_lower = [str(i).strip().lower() for i in income_stmt.index]

        for c in cols:
            r, ni, gp = 0.0, 0.0, 0.0
            for name in ["Total Revenue", "Operating Revenue", "Revenue"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    r = float(val) if pd.notna(val) else 0.0
                    break
            
            for name in ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    ni = float(val) if pd.notna(val) else 0.0
                    break

            for name in ["Gross Profit"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    gp = float(val) if pd.notna(val) else 0.0
                    break

            rev_chart["revenue"].append(round(r / 1e9, 2))
            rev_chart["net_income"].append(round(ni / 1e9, 2))
            rev_chart["gross_margin"].append(round((gp / r) * 100, 1) if r != 0 else 0.0)
            rev_chart["net_margin"].append(round((ni / r) * 100, 1) if r != 0 else 0.0)

    if balance_sheet is not None and not balance_sheet.empty:
        cols = list(balance_sheet.columns)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]
        cash_debt_chart["years"] = years

        index_lower = [str(i).strip().lower() for i in balance_sheet.index]

        for c in cols:
            cash, debt = 0.0, 0.0
            for name in ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"]:
                if name.lower() in index_lower:
                    val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    cash = float(val) if pd.notna(val) else 0.0
                    break

            for name in ["Total Debt", "Long Term Debt", "Current Debt"]:
                if name.lower() in index_lower:
                    val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    debt = float(val) if pd.notna(val) else 0.0
                    break

            cash_debt_chart["cash"].append(round(cash / 1e9, 2))
            cash_debt_chart["debt"].append(round(debt / 1e9, 2))

    return {
        "financial_performance": rev_chart,
        "cash_vs_debt": cash_debt_chart
    }

def prepare_statements_data(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame, cash_flow: pd.DataFrame) -> Dict[str, Any]:
    """Helper to convert financial statement DataFrames into clean JSON for frontend tables."""
    def clean_df(df):
        if df is None or df.empty:
            return {"columns": [], "rows": []}
        cols = [pd.to_datetime(c).strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c)[:10] for c in df.columns]
        rows = []
        for idx in df.index:
            row_vals = []
            for col in df.columns:
                v = df.loc[idx, col]
                if pd.isna(v):
                    row_vals.append(None)
                else:
                    try:
                        row_vals.append(float(v))
                    except Exception:
                        row_vals.append(str(v))
            rows.append({"metric": str(idx), "values": row_vals})
        return {"columns": cols, "rows": rows}

    return {
        "income_statement": clean_df(income_stmt),
        "balance_sheet": clean_df(balance_sheet),
        "cash_flow": clean_df(cash_flow)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True)
