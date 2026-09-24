import yfinance as yf
import pandas as pd
import numpy as np
import re
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sec_filing_validator import get_latest_sec_filing
from sec_facts_validator import validate_core_sec_facts

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
    "Johnson & Johnson (JNJ)": "JNJ",
    "Eli Lilly and Co. (LLY)": "LLY"
}

# Stable SEC registrant identifiers for the curated coverage universe. These
# are identifiers only, never financial values, and let the app query EDGAR
# directly when a market-data response omits filing links.
KNOWN_SEC_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "AMZN": "0001018724",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "META": "0001326801",
    "BRK-B": "0001067983",
    "JPM": "0000019617",
    "JNJ": "0000200406",
    "LLY": "0000059478",
}

KNOWN_SECTORS = {
    # Healthcare
    "LLY": ("Healthcare", "Drug Manufacturers - General", "Eli Lilly and Company"),
    "JNJ": ("Healthcare", "Drug Manufacturers - General", "Johnson & Johnson"),
    "PFE": ("Healthcare", "Drug Manufacturers - General", "Pfizer Inc."),
    "MRK": ("Healthcare", "Drug Manufacturers - General", "Merck & Co., Inc."),
    "ABBV": ("Healthcare", "Drug Manufacturers - General", "AbbVie Inc."),
    "UNH": ("Healthcare", "Healthcare Plans", "UnitedHealth Group Incorporated"),
    "BMY": ("Healthcare", "Drug Manufacturers - General", "Bristol-Myers Squibb Company"),
    "AMGN": ("Healthcare", "Drug Manufacturers - General", "Amgen Inc."),
    "GILD": ("Healthcare", "Drug Manufacturers - General", "Gilead Sciences, Inc."),
    "CVS": ("Healthcare", "Healthcare Plans", "CVS Health Corporation"),
    "CI": ("Healthcare", "Healthcare Plans", "The Cigna Group"),

    # Technology
    "AAPL": ("Technology", "Consumer Electronics", "Apple Inc."),
    "MSFT": ("Technology", "Software - Infrastructure", "Microsoft Corporation"),
    "NVDA": ("Technology", "Semiconductors", "NVIDIA Corporation"),
    "AMD": ("Technology", "Semiconductors", "Advanced Micro Devices, Inc."),
    "INTC": ("Technology", "Semiconductors", "Intel Corporation"),
    "AVGO": ("Technology", "Semiconductors", "Broadcom Inc."),
    "QCOM": ("Technology", "Semiconductors", "QUALCOMM Incorporated"),
    "CRM": ("Technology", "Software - Application", "Salesforce, Inc."),
    "ORCL": ("Technology", "Software - Infrastructure", "Oracle Corporation"),
    "CSCO": ("Technology", "Communication Equipment", "Cisco Systems, Inc."),
    "ADBE": ("Technology", "Software - Infrastructure", "Adobe Inc."),

    # Communication Services
    "GOOGL": ("Communication Services", "Internet Content & Information", "Alphabet Inc. (Google)"),
    "GOOG": ("Communication Services", "Internet Content & Information", "Alphabet Inc. (Google)"),
    "META": ("Communication Services", "Internet Content & Information", "Meta Platforms, Inc."),
    "DIS": ("Communication Services", "Entertainment", "The Walt Disney Company"),
    "NFLX": ("Communication Services", "Entertainment", "Netflix, Inc."),
    "TMUS": ("Communication Services", "Telecom Services", "T-Mobile US, Inc."),
    "VZ": ("Communication Services", "Telecom Services", "Verizon Communications Inc."),
    "T": ("Communication Services", "Telecom Services", "AT&T Inc."),

    # Consumer Cyclical
    "AMZN": ("Consumer Cyclical", "Internet Retail", "Amazon.com, Inc."),
    "TSLA": ("Consumer Cyclical", "Auto Manufacturers", "Tesla, Inc."),
    "HD": ("Consumer Cyclical", "Home Improvement Retail", "The Home Depot, Inc."),
    "LOW": ("Consumer Cyclical", "Home Improvement Retail", "Lowe's Companies, Inc."),
    "NKE": ("Consumer Cyclical", "Footwear & Accessories", "NIKE, Inc."),
    "MCD": ("Consumer Cyclical", "Restaurants", "McDonald's Corporation"),
    "SBUX": ("Consumer Cyclical", "Restaurants", "Starbucks Corporation"),

    # Consumer Staples
    "WMT": ("Consumer Staples", "Discount Stores", "Walmart Inc."),
    "COST": ("Consumer Staples", "Discount Stores", "Costco Wholesale Corporation"),
    "PG": ("Consumer Staples", "Household & Personal Products", "The Procter & Gamble Company"),
    "KO": ("Consumer Staples", "Beverages - Non-Alcoholic", "The Coca-Cola Company"),
    "PEP": ("Consumer Staples", "Beverages - Non-Alcoholic", "PepsiCo, Inc."),
    "PM": ("Consumer Staples", "Tobacco", "Philip Morris International Inc."),

    # Financial Services
    "JPM": ("Financial Services", "Banks - Diversified", "JPMorgan Chase & Co."),
    "BAC": ("Financial Services", "Banks - Diversified", "Bank of America Corporation"),
    "WFC": ("Financial Services", "Banks - Diversified", "Wells Fargo & Company"),
    "C": ("Financial Services", "Banks - Diversified", "Citigroup Inc."),
    "GS": ("Financial Services", "Capital Markets", "The Goldman Sachs Group, Inc."),
    "MS": ("Financial Services", "Capital Markets", "Morgan Stanley"),
    "BRK-B": ("Financial Services", "Financial - Conglomerates", "Berkshire Hathaway Inc."),
    "V": ("Financial Services", "Credit Services", "Visa Inc."),
    "MA": ("Financial Services", "Credit Services", "Mastercard Incorporated"),

    # Energy
    "XOM": ("Energy", "Oil & Gas Integrated", "Exxon Mobil Corporation"),
    "CVX": ("Energy", "Oil & Gas Integrated", "Chevron Corporation"),
    "COP": ("Energy", "Oil & Gas E&P", "ConocoPhillips"),

    # Industrials
    "CAT": ("Industrials", "Farm & Heavy Construction Machinery", "Caterpillar Inc."),
    "DE": ("Industrials", "Farm & Heavy Construction Machinery", "Deere & Company"),
    "GE": ("Industrials", "Specialty Industrial Machinery", "General Electric Company"),
    "HON": ("Industrials", "Conglomerates", "Honeywell International Inc."),
    "BA": ("Industrials", "Aerospace & Defense", "The Boeing Company"),
    "RTX": ("Industrials", "Aerospace & Defense", "RTX Corporation")
}

# Production financial values are fetched live; no static financial snapshots are retained.
# Cache Store
_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 900
ERROR_CACHE_TTL = 60
MAX_CACHE_ENTRIES = 8

def normalize_statement(df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Return a numeric statement with unique periods ordered newest first."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    normalized = df.copy()
    parsed_columns = pd.to_datetime(normalized.columns, errors="coerce")
    valid_positions = [i for i, value in enumerate(parsed_columns) if not pd.isna(value)]
    if not valid_positions:
        return pd.DataFrame()

    normalized = normalized.iloc[:, valid_positions]
    normalized.columns = pd.DatetimeIndex([parsed_columns[i] for i in valid_positions])
    normalized = normalized.loc[:, ~normalized.columns.duplicated(keep="first")]
    normalized = normalized.sort_index(axis=1, ascending=False)
    normalized = normalized.apply(pd.to_numeric, errors="coerce")
    normalized = normalized.dropna(axis=0, how="all").dropna(axis=1, how="all")
    return normalized


def _ticker_frame(ticker: Any, *attribute_names: str) -> pd.DataFrame:
    """Read the first non-empty statement exposed by the provider."""
    for name in attribute_names:
        try:
            value = getattr(ticker, name)
        except Exception:
            continue
        normalized = normalize_statement(value)
        if not normalized.empty:
            return normalized
    return pd.DataFrame()


def _latest_period(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if df is None or df.empty:
        return None
    try:
        return pd.Timestamp(df.columns[0]).tz_localize(None)
    except Exception:
        return None


def _select_latest_balance_sheet(annual: pd.DataFrame, quarterly: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    annual_period = _latest_period(annual)
    quarterly_period = _latest_period(quarterly)
    if quarterly_period is not None and (annual_period is None or quarterly_period >= annual_period):
        return quarterly, "latest_quarter"
    if annual_period is not None:
        return annual, "latest_annual"
    return pd.DataFrame(), "unavailable"


def _select_flow_statement(ttm: pd.DataFrame, annual: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    if ttm is not None and not ttm.empty:
        return ttm, "trailing_twelve_months"
    if annual is not None and not annual.empty:
        return annual, "latest_annual_fallback"
    return pd.DataFrame(), "unavailable"


def _is_financial_institution(info: Dict[str, Any]) -> bool:
    """Identify institutions needing bank/insurer-specific analysis.

    Broad `Financial Services` sector membership is not enough: payment
    networks such as Visa and Mastercard still have ordinary current-asset and
    operating-profit statements and should not be treated as banks.
    """
    industry = str(info.get("industry") or "").lower()
    institution_terms = (
        "bank", "insurance", "capital markets", "financial conglomerate",
        "financial - conglomerate", "mortgage finance", "asset management",
        "credit services - banks", "savings & loan", "credit union",
    )
    return any(term in industry for term in institution_terms)


def _iso_period(df: pd.DataFrame) -> Optional[str]:
    period = _latest_period(df)
    return period.date().isoformat() if period is not None else None


def _period_age_days(period_text: Optional[str]) -> Optional[int]:
    if not period_text:
        return None
    try:
        return max(0, (datetime.now(timezone.utc).date() - datetime.fromisoformat(period_text).date()).days)
    except (TypeError, ValueError):
        return None


def _period_is_materially_newer(
    filed_period: Optional[str],
    provider_period: Optional[str],
    tolerance_days: int = 14,
) -> bool:
    """Allow small fiscal-calendar normalization differences between sources."""
    if not filed_period or not provider_period:
        return False
    try:
        filed_date = datetime.fromisoformat(filed_period).date()
        provider_date = datetime.fromisoformat(provider_period).date()
    except (TypeError, ValueError):
        return False
    return (filed_date - provider_date).days > tolerance_days


def _provider_cik(ticker: Any) -> Optional[str]:
    """Extract a CIK hint from provider filing links, then verify at SEC."""
    try:
        filings = ticker.sec_filings or []
    except Exception:
        return None
    for filing in filings:
        for url in (filing.get("exhibits") or {}).values():
            match = re.search(r"/sec-filings/(\d{1,10})/", str(url))
            if match:
                return match.group(1).zfill(10)
        match = re.search(r"_(\d{1,10})(?:$|\D)", str(filing.get("edgarUrl") or ""))
        if match:
            return match.group(1).zfill(10)
    return None


def _usable_market_value(value: Any) -> bool:
    """Return True only for source values that can safely be published."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return bool(np.isfinite(value))
    except (TypeError, ValueError):
        return True


def _set_market_value_if_missing(info: Dict[str, Any], key: str, value: Any) -> bool:
    if _usable_market_value(info.get(key)) or not _usable_market_value(value):
        return False
    info[key] = value
    return True


def _read_mapping_value(mapping: Any, *keys: str) -> Any:
    """Read lazy provider mappings without allowing one failed key to abort a run."""
    for key in keys:
        try:
            value = mapping.get(key) if hasattr(mapping, "get") else mapping[key]
        except Exception:
            continue
        if _usable_market_value(value):
            return value
    return None


def _enrich_info_with_live_market_fallbacks(ticker: Any, raw_info: Any) -> Dict[str, Any]:
    """Fill missing quote-summary fields from independent live Yahoo routes.

    Yahoo's quote-summary/profile route can return an empty payload from a
    hosted server while its chart and fast-quote routes continue to work. This
    function merges only live provider values; it never supplies stored prices
    or estimates.
    """
    info = dict(raw_info) if isinstance(raw_info, dict) else {}
    recovered_fields = []

    try:
        fast_info = ticker.fast_info
    except Exception:
        fast_info = {}

    fast_field_map = {
        "regularMarketPrice": ("lastPrice",),
        "currentPrice": ("lastPrice",),
        "previousClose": ("regularMarketPreviousClose", "previousClose"),
        "marketCap": ("marketCap",),
        "sharesOutstanding": ("shares",),
        "currency": ("currency",),
        "exchange": ("exchange",),
        "quoteType": ("quoteType",),
        "fiftyTwoWeekHigh": ("yearHigh",),
        "fiftyTwoWeekLow": ("yearLow",),
    }
    for destination, source_keys in fast_field_map.items():
        if _set_market_value_if_missing(
            info,
            destination,
            _read_mapping_value(fast_info, *source_keys),
        ):
            recovered_fields.append(destination)

    # The chart route provides a second independent source for price/range and
    # also makes a zero dividend distinguishable from missing dividend data.
    try:
        market_history = ticker.history(
            period="1y",
            auto_adjust=False,
            actions=True,
            raise_errors=False,
        )
    except Exception:
        market_history = pd.DataFrame()
    if isinstance(market_history, pd.DataFrame) and not market_history.empty:
        closes = (
            pd.to_numeric(market_history["Close"], errors="coerce").dropna()
            if "Close" in market_history else pd.Series(dtype=float)
        )
        highs = (
            pd.to_numeric(market_history["High"], errors="coerce").dropna()
            if "High" in market_history else pd.Series(dtype=float)
        )
        lows = (
            pd.to_numeric(market_history["Low"], errors="coerce").dropna()
            if "Low" in market_history else pd.Series(dtype=float)
        )
        if not closes.empty:
            latest_close = float(closes.iloc[-1])
            prior_close = float(closes.iloc[-2]) if len(closes) > 1 else None
            for key, value in (
                ("regularMarketPrice", latest_close),
                ("currentPrice", latest_close),
                ("previousClose", prior_close),
            ):
                if _set_market_value_if_missing(info, key, value):
                    recovered_fields.append(key)
        if not highs.empty and _set_market_value_if_missing(info, "fiftyTwoWeekHigh", float(highs.max())):
            recovered_fields.append("fiftyTwoWeekHigh")
        if not lows.empty and _set_market_value_if_missing(info, "fiftyTwoWeekLow", float(lows.min())):
            recovered_fields.append("fiftyTwoWeekLow")
        if not _usable_market_value(info.get("dividendRate")) and "Dividends" in market_history:
            dividends = pd.to_numeric(market_history["Dividends"], errors="coerce").dropna()
            info["dividendRate"] = float(dividends.sum()) if not dividends.empty else 0.0
            info["dividendRateBasis"] = "trailing_twelve_months_cash_dividends"
            recovered_fields.append("dividendRate")

    try:
        metadata = ticker.get_history_metadata() or {}
    except Exception:
        metadata = {}
    metadata_field_map = {
        "regularMarketTime": ("regularMarketTime",),
        "currency": ("currency",),
        "exchange": ("exchangeName",),
        "quoteType": ("instrumentType",),
    }
    for destination, source_keys in metadata_field_map.items():
        if _set_market_value_if_missing(
            info,
            destination,
            _read_mapping_value(metadata, *source_keys),
        ):
            recovered_fields.append(destination)

    if not _usable_market_value(info.get("targetMeanPrice")):
        try:
            targets = ticker.analyst_price_targets or {}
        except Exception:
            targets = {}
        if _set_market_value_if_missing(info, "targetMeanPrice", _read_mapping_value(targets, "mean")):
            recovered_fields.append("targetMeanPrice")

    if _usable_market_value(info.get("dividendRate")) and not info.get("dividendRateBasis"):
        info["dividendRateBasis"] = "provider_forward_annual_rate"
    info["market_data_route"] = "quote_summary+live_fallbacks" if recovered_fields else "quote_summary"
    info["market_data_recovered_fields"] = sorted(set(recovered_fields))
    return info

def fetch_stock_data(ticker_symbol: str, force_refresh: bool = False) -> Dict[str, Any]:
    symbol = ticker_symbol.strip().upper()
    if not symbol:
        symbol = "AAPL"

    now = time.time()
    if not force_refresh and symbol in _CACHE:
        cached_entry = _CACHE[symbol]
        ttl = ERROR_CACHE_TTL if cached_entry["data"].get("error") else CACHE_TTL
        if now - cached_entry["timestamp"] < ttl:
            return cached_entry["data"]

    result = None
    fetch_error = None

    # Every production request uses the live provider. Missing live fields remain
    # missing; the application never falls back to static estimates or snapshots.
    try:
        ticker = yf.Ticker(symbol)
        try:
            raw_info = ticker.info or {}
        except Exception:
            raw_info = {}
        info = _enrich_info_with_live_market_fallbacks(ticker, raw_info)
        quote_type = str(info.get("quoteType") or "").strip().upper()
        if quote_type and quote_type != "EQUITY":
            raise ValueError(
                f"{symbol} is classified as {quote_type}, not a public-company equity. "
                "StatementIQ analyzes operating-company financial statements rather than funds, indexes, currencies, or derivatives."
            )
        income_stmt = _ticker_frame(ticker, "income_stmt", "financials")
        balance_sheet = _ticker_frame(ticker, "balance_sheet", "bs")
        cash_flow = _ticker_frame(ticker, "cashflow", "cash_flow")
        quarterly_income_stmt = _ticker_frame(ticker, "quarterly_income_stmt", "quarterly_financials")
        quarterly_balance_sheet = _ticker_frame(ticker, "quarterly_balance_sheet", "quarterly_bs")
        quarterly_cash_flow = _ticker_frame(ticker, "quarterly_cashflow", "quarterly_cash_flow")
        ttm_income_stmt = _ticker_frame(ticker, "ttm_income_stmt")
        ttm_cash_flow = _ticker_frame(ticker, "ttm_cashflow")
        # Price history is not used by the statement analysis. Avoid an extra
        # provider request so searches for arbitrary companies return faster.
        history = pd.DataFrame()

        # Only fill descriptive labels from the maintained symbol directory. No
        # numerical financial or market value is supplied by this mapping.
        if symbol in KNOWN_SECTORS:
            sec, ind, long_n = KNOWN_SECTORS[symbol]
            info.setdefault("sector", sec)
            info.setdefault("industry", ind)
            info.setdefault("longName", long_n)

        market_time = info.get("regularMarketTime")
        if market_time is not None:
            try:
                info["market_data_as_of"] = datetime.fromtimestamp(float(market_time), tz=timezone.utc).isoformat()
            except (TypeError, ValueError, OSError):
                info["market_data_as_of"] = None
        else:
            info["market_data_as_of"] = None
        info["market_data_provider"] = "Yahoo Finance"
        info["statement_data_provider"] = "Yahoo Finance"
        info["data_source"] = "live"

        is_fin = _is_financial_institution(info)

        analysis_income_stmt, income_basis = _select_flow_statement(ttm_income_stmt, income_stmt)
        analysis_cash_flow, cash_flow_basis = _select_flow_statement(ttm_cash_flow, cash_flow)
        analysis_balance_sheet, balance_basis = _select_latest_balance_sheet(balance_sheet, quarterly_balance_sheet)

        analysis_periods = {
            "income": _iso_period(analysis_income_stmt),
            "balance_sheet": _iso_period(analysis_balance_sheet),
            "cash_flow": _iso_period(analysis_cash_flow),
        }
        analysis_period_ages = {
            name: _period_age_days(period)
            for name, period in analysis_periods.items()
        }
        latest_statement_period = max(
            (p for p in [
                _latest_period(analysis_income_stmt),
                _latest_period(analysis_balance_sheet),
                _latest_period(analysis_cash_flow),
            ] if p is not None),
            default=None,
        )
        latest_statement_period_text = latest_statement_period.date().isoformat() if latest_statement_period is not None else None
        statement_age_days = _period_age_days(latest_statement_period_text)
        sec_filing = get_latest_sec_filing(
            symbol,
            cik_hint=_provider_cik(ticker) or KNOWN_SEC_CIKS.get(symbol),
        )
        sec_fact_validation = validate_core_sec_facts(
            sec_filing.get("cik") if sec_filing.get("status") == "verified" else None,
            quarterly_income_stmt,
            quarterly_balance_sheet,
            info.get("financialCurrency") or info.get("currency"),
        )

        quality_warnings = []
        if income_basis != "trailing_twelve_months":
            quality_warnings.append("Trailing-twelve-month income data was unavailable; the latest annual income statement is used.")
        if balance_basis != "latest_quarter":
            quality_warnings.append("A newer quarterly balance sheet was unavailable; the latest annual balance sheet is used.")
        if cash_flow_basis != "trailing_twelve_months":
            quality_warnings.append("Trailing-twelve-month cash-flow data was unavailable; the latest annual cash-flow statement is used.")
        stale_periods = [
            f"{name.replace('_', ' ')} ({age} days)"
            for name, age in analysis_period_ages.items()
            if age is not None and age > 180
        ]
        if stale_periods:
            quality_warnings.append(
                "These analysis periods are more than 180 days old: " + ", ".join(stale_periods) + "."
            )
        market_currency = info.get("currency")
        statement_currency = info.get("financialCurrency") or market_currency
        if market_currency and statement_currency and str(market_currency).upper() != str(statement_currency).upper():
            quality_warnings.append(
                f"Market values are in {market_currency} while statements are in {statement_currency}; enterprise value and EV/EBITDA are withheld."
            )
        if sec_filing.get("status") == "unavailable":
            quality_warnings.append(sec_filing.get("reason") or "SEC filing-recency validation was unavailable.")
        if sec_fact_validation.get("status") == "mismatch":
            mismatch_names = ", ".join(item["metric"] for item in sec_fact_validation.get("mismatches", []))
            quality_warnings.append(f"Provider values differed from comparable SEC Company Facts for: {mismatch_names}.")
        elif sec_filing.get("status") == "verified" and sec_fact_validation.get("status") == "unavailable":
            quality_warnings.append(
                sec_fact_validation.get("reason") or "Comparable SEC Company Facts were unavailable for numeric cross-checking."
            )

        if is_fin:
            quality_warnings.append(
                "The headline score is withheld for banks and insurers because a reliable institution analysis also requires "
                "regulatory capital, asset quality, funding, loss-reserve, and net-interest measures not present in standardized statements."
            )

        sec_report_period = sec_filing.get("report_period") if sec_filing.get("status") == "verified" else None
        lagging_statement_types = [
            name.replace("_", " ")
            for name, provider_period in analysis_periods.items()
            if _period_is_materially_newer(sec_report_period, provider_period)
        ]
        provider_lags_latest_filing = bool(lagging_statement_types)
        if provider_lags_latest_filing:
            quality_warnings.append(
                f"SEC shows a newer filed report period ({sec_report_period}) than the provider's "
                f"{', '.join(lagging_statement_types)} analysis period."
            )

        integrity_hold_reason = None
        if sec_fact_validation.get("status") == "mismatch":
            integrity_hold_reason = "Headline score withheld because comparable provider and SEC statement facts did not agree."
        elif provider_lags_latest_filing:
            integrity_hold_reason = "Headline score withheld until the provider includes the newest filed report period."
        # Sector-model applicability is handled by the connected scoring model,
        # not by the data-integrity gate. Keep this field exclusively for source
        # mismatches or provider lag so the UI can distinguish the two cases.

        if income_stmt is not None and not income_stmt.empty and balance_sheet is not None and not balance_sheet.empty:
            result = {
                "symbol": symbol,
                "is_financial_sector": is_fin,
                "info": info,
                "income_stmt": income_stmt,
                "balance_sheet": balance_sheet,
                "cash_flow": cash_flow if cash_flow is not None else pd.DataFrame(),
                "quarterly_income_stmt": quarterly_income_stmt,
                "quarterly_balance_sheet": quarterly_balance_sheet,
                "quarterly_cash_flow": quarterly_cash_flow,
                "analysis_income_stmt": analysis_income_stmt,
                "analysis_balance_sheet": analysis_balance_sheet,
                "analysis_cash_flow": analysis_cash_flow,
                "analysis_basis": {
                    "income": income_basis,
                    "income_period_end": analysis_periods["income"],
                    "income_age_days": analysis_period_ages["income"],
                    "balance_sheet": balance_basis,
                    "balance_sheet_period_end": analysis_periods["balance_sheet"],
                    "balance_sheet_age_days": analysis_period_ages["balance_sheet"],
                    "cash_flow": cash_flow_basis,
                    "cash_flow_period_end": analysis_periods["cash_flow"],
                    "cash_flow_age_days": analysis_period_ages["cash_flow"],
                    "latest_statement_period": latest_statement_period_text,
                    "statement_age_days": statement_age_days,
                },
                "sec_filing": sec_filing,
                "sec_fact_validation": sec_fact_validation,
                "verification_scope": "SEC validation checks filing recency and comparable latest-quarter core facts; TTM and other rows remain provider-standardized figures.",
                "integrity_hold_reason": integrity_hold_reason,
                "provider_lags_latest_filing": provider_lags_latest_filing,
                "quality_warnings": quality_warnings,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "history": history if history is not None else pd.DataFrame(),
                "error": None
            }
        else:
            fetch_error = "The live provider did not return complete income-statement and balance-sheet data."
    except Exception as exc:
        fetch_error = f"The live provider request failed: {exc}"

    if result is None:
        sec, industry, _ = KNOWN_SECTORS.get(symbol, ("", "", symbol))
        is_fin = _is_financial_institution({"sector": sec, "industry": industry})
        result = {
            "symbol": symbol,
            "is_financial_sector": is_fin,
            "info": {"symbol": symbol, "data_source": "unavailable"},
            "income_stmt": pd.DataFrame(),
            "balance_sheet": pd.DataFrame(),
            "cash_flow": pd.DataFrame(),
            "quarterly_income_stmt": pd.DataFrame(),
            "quarterly_balance_sheet": pd.DataFrame(),
            "quarterly_cash_flow": pd.DataFrame(),
            "analysis_income_stmt": pd.DataFrame(),
            "analysis_balance_sheet": pd.DataFrame(),
            "analysis_cash_flow": pd.DataFrame(),
            "analysis_basis": {},
            "sec_filing": {"status": "unavailable", "reason": "No live statement data was available to validate."},
            "sec_fact_validation": {"status": "unavailable", "checked": 0, "matched": 0, "mismatches": []},
            "verification_scope": "No filing validation was possible because live statement data was unavailable.",
            "quality_warnings": [],
            "history": pd.DataFrame(),
            "error": f"Live financial data for {symbol} is unavailable. {fetch_error or ''} No substitute values were used.".strip()
        }

    _CACHE[symbol] = {"timestamp": now, "data": result}
    if len(_CACHE) > MAX_CACHE_ENTRIES:
        oldest_symbol = min(_CACHE, key=lambda key: _CACHE[key]["timestamp"])
        if oldest_symbol != symbol:
            _CACHE.pop(oldest_symbol, None)
    return result
