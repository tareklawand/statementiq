import os
import json
import io
import sys
import threading
import re
from contextlib import asynccontextmanager
import pandas as pd
import numpy as np

sys.path.append('/Users/tareklawand/Library/Python/3.9/lib/python/site-packages')

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any

from data_fetcher import fetch_stock_data, PRESET_TICKERS
from metrics_calculator import compute_metrics
from deterministic_analyst import generate_ai_insights
from pdf_generator import generate_pdf_report
from statement_analysis import prepare_statement_analysis
from sector_analysis import prepare_sector_analysis
from filing_disclosure_analyzer import scan_annual_filing


@asynccontextmanager
async def lifespan(_: FastAPI):
    threading.Thread(target=prewarm_cache, daemon=True).start()
    yield


app = FastAPI(title="StatementIQ Financial API", lifespan=lifespan)

# Mount static files directory
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,23}$")


def normalize_ticker(value: str) -> str:
    symbol = (value or "").strip().upper()
    if not TICKER_PATTERN.fullmatch(symbol):
        raise HTTPException(
            status_code=400,
            detail="Enter a valid public-company ticker using letters, numbers, a period, or a hyphen.",
        )
    return symbol


def calculate_dividend_yield(info: Dict[str, Any], share_price: Optional[float]) -> Optional[float]:
    """Return forward annualized dividend yield from rate and current price.

    The provider's dividendYield field has changed units across API versions, so
    using dividendRate / price avoids silently displaying 100x the true yield.
    """
    annual_dividend = info.get("dividendRate")
    try:
        if annual_dividend is None or share_price is None:
            return None
        annual_dividend = float(annual_dividend)
        share_price = float(share_price)
        if annual_dividend < 0 or share_price <= 0:
            return None
        return annual_dividend / share_price
    except (TypeError, ValueError):
        return None

def prewarm_cache():
    """Warm only the default company without loading every statement into RAM."""
    print("⚡ Pre-warming default financial data...")
    try:
        fetch_stock_data("AAPL")
    except Exception:
        pass
    print("✅ Default pre-warm complete!")

@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serves the main custom web application frontend with cache-busting headers."""
    index_path = os.path.join("static", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            headers = {"Cache-Control": "no-cache, no-store, must-revalidate, max-age=0"}
            return HTMLResponse(content=f.read(), headers=headers)
    return "<h1>StatementIQ UI loading...</h1>"


@app.get("/health")
def health_check():
    """Uptime health check endpoint for monitoring and Render deployment."""
    return {"status": "healthy", "service": "StatementIQ Engine"}

@app.get("/api/presets")
def get_presets():
    """Returns preset tickers list."""
    return {"presets": PRESET_TICKERS}


@app.get("/{asset_name}", include_in_schema=False)
def read_root_asset(asset_name: str):
    """Serve root-level public assets consistently in local and edge hosting."""
    allowed_assets = {
        "favicon.svg", "favicon.ico", "favicon-iq-48.png", "favicon-48.png",
        "favicon-512.png", "apple-touch-icon.png", "robots.txt", "sitemap.xml",
    }
    if asset_name not in allowed_assets:
        raise HTTPException(status_code=404, detail="Not found")
    asset_path = os.path.join("static", asset_name)
    if not os.path.exists(asset_path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(asset_path)


@app.get("/api/analyze")
def analyze_ticker(
    ticker: str = Query(..., description="Stock Ticker Symbol"),
    refresh: bool = Query(False, description="Bypass the short-lived data cache"),
    api_key: Optional[str] = Query(None),
):
    """
    Fetches current financial data, computes connected health and valuation diagnostics,
    prepares chart data, and generates a deterministic evidence briefing.
    """
    symbol = normalize_ticker(ticker)

    stock_data = fetch_stock_data(symbol, force_refresh=refresh)
    if stock_data.get("error"):
        raise HTTPException(status_code=400, detail=stock_data["error"])

    info = stock_data.get("info", {})
    metrics = compute_metrics(stock_data)
    share_price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")

    company_name = info.get("longName") or info.get("shortName") or symbol

    ai_insights = generate_ai_insights(
        company_name=company_name,
        symbol=symbol,
        health_score=metrics["health_score"],
        ratios_summary=metrics["ratio_evaluations"],
        api_key=api_key,
        score_coverage=metrics.get("score_coverage"),
    )

    income_stmt = stock_data.get("income_stmt", pd.DataFrame())
    balance_sheet = stock_data.get("balance_sheet", pd.DataFrame())
    
    charts_data = prepare_charts_data(income_stmt, balance_sheet)
    statements_data = prepare_statements_data(
        income_stmt,
        balance_sheet,
        stock_data.get("cash_flow", pd.DataFrame()),
        stock_data.get("quarterly_income_stmt", pd.DataFrame()),
        stock_data.get("quarterly_balance_sheet", pd.DataFrame()),
        stock_data.get("quarterly_cash_flow", pd.DataFrame()),
    )
    statement_analysis = prepare_statement_analysis(
        income_stmt,
        balance_sheet,
        stock_data.get("cash_flow", pd.DataFrame()),
        stock_data.get("quarterly_income_stmt", pd.DataFrame()),
    )
    sector_analysis = prepare_sector_analysis(stock_data, metrics)
    sec_filing = stock_data.get("sec_filing") or {}
    annual_filing = (sec_filing.get("key_filings") or {}).get("annual") or {}
    filing_disclosure_review = scan_annual_filing(annual_filing.get("filing_url"))

    return {
        "symbol": symbol,
        "company_name": company_name,
        "info": {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "currency": info.get("financialCurrency") or info.get("currency"),
            "market_currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "price": share_price,
            "market_cap": metrics["ev_breakdown"].get("market_cap"),
            "market_cap_method": metrics["ev_breakdown"].get("market_cap_method"),
            "enterprise_value": metrics["ev_breakdown"].get("enterprise_value_std"),
            "pe_ratio": metrics["ratios"].get("pe_ratio"),
            "ev_ebitda": metrics["ratios"].get("ev_ebitda"),
            "fifty_two_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_low": info.get("fiftyTwoWeekLow"),
            "dividend_yield": calculate_dividend_yield(info, share_price),
            "dividend_yield_basis": info.get("dividendRateBasis"),
            "target_price": info.get("targetMeanPrice"),
        },
        "data_quality": {
            "source_mode": info.get("data_source"),
            "statement_provider": info.get("statement_data_provider"),
            "market_provider": info.get("market_data_provider"),
            "market_data_route": info.get("market_data_route"),
            "market_data_as_of": info.get("market_data_as_of"),
            "fetched_at": stock_data.get("fetched_at"),
            "analysis_basis": stock_data.get("analysis_basis") or {},
            "sec_filing": stock_data.get("sec_filing") or {},
            "sec_fact_validation": stock_data.get("sec_fact_validation") or {},
            "calculation_coverage": metrics.get("calculation_coverage") or {},
            "verification_scope": stock_data.get("verification_scope"),
            "integrity_hold_reason": stock_data.get("integrity_hold_reason"),
            "warnings": stock_data.get("quality_warnings") or [],
            "missing_values_policy": "Missing source values remain N/A; no static or estimated fallback is used."
        },
        "metrics": metrics,
        "ai_insights": ai_insights,
        "charts": charts_data,
        "statements": statements_data,
        "statement_analysis": statement_analysis,
        "sector_analysis": sector_analysis,
        "filing_disclosure_review": filing_disclosure_review,
    }

class PDFRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str

@app.post("/api/download-pdf")
def download_pdf(payload: PDFRequest):
    """Generate a report exclusively from server-fetched, server-calculated data."""
    try:
        symbol = normalize_ticker(payload.symbol)
        stock_data = fetch_stock_data(symbol, force_refresh=True)
        if stock_data.get("error"):
            raise HTTPException(status_code=400, detail=stock_data["error"])
        info = stock_data.get("info") or {}
        company_name = info.get("longName") or info.get("shortName") or symbol
        metrics = compute_metrics(stock_data)
        ai_insights = generate_ai_insights(
            company_name=company_name,
            symbol=symbol,
            health_score=metrics["health_score"],
            ratios_summary=metrics["ratio_evaluations"],
            score_coverage=metrics.get("score_coverage"),
        )
        pdf_buf = generate_pdf_report(
            company_name=company_name,
            symbol=symbol,
            metrics=metrics,
            ai_insights=ai_insights,
            data_quality={
                "analysis_basis": stock_data.get("analysis_basis") or {},
                "sec_filing": stock_data.get("sec_filing") or {},
                "sec_fact_validation": stock_data.get("sec_fact_validation") or {},
                "calculation_coverage": metrics.get("calculation_coverage") or {},
                "verification_scope": stock_data.get("verification_scope"),
                "integrity_hold_reason": stock_data.get("integrity_hold_reason"),
                "warnings": stock_data.get("quality_warnings") or [],
                "fetched_at": stock_data.get("fetched_at"),
            },
        )
        return StreamingResponse(
            pdf_buf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={symbol}_Financial_Audit_Report.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def prepare_charts_data(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame) -> Dict[str, Any]:
    """Helper to extract clean series arrays for frontend charts."""
    rev_chart = {"years": [], "revenue": [], "net_income": [], "gross_margin": [], "net_margin": []}
    cash_debt_chart = {"years": [], "cash": [], "debt": []}

    if income_stmt is not None and not income_stmt.empty:
        cols = sorted(list(income_stmt.columns), reverse=True)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]
        rev_chart["years"] = years

        index_lower = [str(i).strip().lower() for i in income_stmt.index]

        for c in cols:
            r, ni, gp = None, None, None
            for name in ["Total Revenue", "Operating Revenue", "Revenue"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    r = float(val) if pd.notna(val) else None
                    break
            
            for name in ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    ni = float(val) if pd.notna(val) else None
                    break

            for name in ["Gross Profit"]:
                if name.lower() in index_lower:
                    val = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    gp = float(val) if pd.notna(val) else None
                    break

            rev_chart["revenue"].append(round(r / 1e9, 2) if r is not None else None)
            rev_chart["net_income"].append(round(ni / 1e9, 2) if ni is not None else None)
            rev_chart["gross_margin"].append(round((gp / r) * 100, 1) if gp is not None and r not in (None, 0) else None)
            rev_chart["net_margin"].append(round((ni / r) * 100, 1) if ni is not None and r not in (None, 0) else None)

    if balance_sheet is not None and not balance_sheet.empty:
        cols = sorted(list(balance_sheet.columns), reverse=True)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]
        cash_debt_chart["years"] = years

        index_lower = [str(i).strip().lower() for i in balance_sheet.index]

        for c in cols:
            cash, debt = None, None
            for name in ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"]:
                if name.lower() in index_lower:
                    val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    cash = float(val) if pd.notna(val) else None
                    break

            # When the provider supplies cash and short-term investments as
            # separate lines, display their sum rather than cash alone.
            if "cash cash equivalents and short term investments" not in index_lower and cash is not None:
                for name in ["Other Short Term Investments", "Current Investments"]:
                    if name.lower() in index_lower:
                        val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                        if pd.notna(val):
                            cash += float(val)
                        break

            for name in ["Total Debt"]:
                if name.lower() in index_lower:
                    val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    debt = float(val) if pd.notna(val) else None
                    break

            if debt is None:
                current_debt = None
                long_term_debt = None
                for name in ["Current Debt", "Current Debt And Capital Lease Obligation"]:
                    if name.lower() in index_lower:
                        val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                        current_debt = float(val) if pd.notna(val) else None
                        break
                for name in ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"]:
                    if name.lower() in index_lower:
                        val = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                        long_term_debt = float(val) if pd.notna(val) else None
                        break
                if current_debt is not None and long_term_debt is not None:
                    debt = current_debt + long_term_debt

            cash_debt_chart["cash"].append(round(cash / 1e9, 2) if cash is not None else None)
            cash_debt_chart["debt"].append(round(debt / 1e9, 2) if debt is not None else None)

    return {
        "financial_performance": rev_chart,
        "cash_vs_debt": cash_debt_chart
    }

def prepare_statements_data(
    income_stmt: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cash_flow: pd.DataFrame,
    quarterly_income_stmt: Optional[pd.DataFrame] = None,
    quarterly_balance_sheet: Optional[pd.DataFrame] = None,
    quarterly_cash_flow: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
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
        "cash_flow": clean_df(cash_flow),
        "quarterly_income_statement": clean_df(quarterly_income_stmt),
        "quarterly_balance_sheet": clean_df(quarterly_balance_sheet),
        "quarterly_cash_flow": clean_df(quarterly_cash_flow),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True)
