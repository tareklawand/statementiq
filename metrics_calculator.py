import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

def get_row_value(df: pd.DataFrame, posibles_names: list, col_idx: int = 0) -> Optional[float]:
    if df is None or df.empty:
        return None
    
    df_index_lower = [str(idx).strip().lower() for idx in df.index]
    
    for name in posibles_names:
        name_lower = name.strip().lower()
        if name_lower in df_index_lower:
            matched_idx = df_index_lower.index(name_lower)
            try:
                val = df.iloc[matched_idx, col_idx]
                if pd.notna(val) and not np.isnan(float(val)):
                    return float(val)
            except Exception:
                continue
    return None

def compute_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info", {})
    symbol = (data.get("symbol") or info.get("symbol") or "").strip().upper()
    sector = info.get("sector", "")
    
    # Financial Services Sector Detection (Banks, Insurers, Conglomerates)
    financial_tickers = {"JPM", "BRK-B", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "AXP", "BLK"}
    is_financial_sector = (
        symbol in financial_tickers or
        data.get("is_financial_sector", False) or
        any(kw in str(sector).lower() for kw in ["financial", "bank", "insurance"])
    )

    income_stmt = data.get("income_stmt", pd.DataFrame())
    balance_sheet = data.get("balance_sheet", pd.DataFrame())
    cash_flow = data.get("cash_flow", pd.DataFrame())
    
    col = 0
    
    # Raw Financial Items (Full Float Precision or None)
    revenue = get_row_value(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue", "Interest Income", "Total Interest Income"], col)
    gross_profit = get_row_value(income_stmt, ["Gross Profit"], col)
    net_income = get_row_value(income_stmt, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"], col)
    operating_income = get_row_value(income_stmt, ["Operating Income", "Net Interest Income"], col)
    depreciation_amortization = get_row_value(cash_flow, ["Depreciation & Amortization", "Depreciation And Amortization", "DepreciationAmortizationDepletion"], col)
    reported_ebitda = get_row_value(income_stmt, ["EBITDA", "Normalized EBITDA"], col)

    # Never treat a missing D&A line as zero. Prefer reported EBITDA; otherwise
    # derive it only when both inputs are explicitly available.
    if reported_ebitda is not None:
        ebitda = reported_ebitda
        ebitda_method = "reported"
    elif operating_income is not None and depreciation_amortization is not None:
        ebitda = operating_income + depreciation_amortization
        ebitda_method = "operating_income_plus_d_and_a"
    else:
        ebitda = None
        ebitda_method = None
    
    total_assets = get_row_value(balance_sheet, ["Total Assets"], col)
    total_assets_prev = get_row_value(balance_sheet, ["Total Assets"], col + 1)
    
    avg_total_assets = (
        (total_assets + total_assets_prev) / 2.0
        if total_assets is not None and total_assets_prev is not None
        else None
    )

    current_assets = get_row_value(balance_sheet, ["Current Assets", "Total Current Assets"], col)
    current_liabilities = get_row_value(balance_sheet, ["Current Liabilities", "Total Current Liabilities"], col)
    
    combined_cash_and_investments = get_row_value(balance_sheet, ["Cash Cash Equivalents And Short Term Investments"], col)
    cash_and_equiv = get_row_value(balance_sheet, ["Cash And Cash Equivalents", "Cash Financial"], col)
    current_marketable = get_row_value(balance_sheet, ["Other Short Term Investments"], col)
    if combined_cash_and_investments is not None:
        cash_and_short_term = combined_cash_and_investments
    elif cash_and_equiv is not None:
        cash_and_short_term = cash_and_equiv + (current_marketable if current_marketable is not None else 0.0)
    else:
        cash_and_short_term = None

    accounts_receivable = get_row_value(balance_sheet, ["Accounts Receivable", "Current Receivables"], col)
    aggregate_receivables = get_row_value(balance_sheet, ["Receivables"], col)
    vendor_nontrade = get_row_value(balance_sheet, ["Vendor Nontrade Receivables"], col)
    if aggregate_receivables is not None:
        # Prefer the provider's aggregate current receivables line so disclosed
        # components are neither omitted nor counted twice.
        receivables = aggregate_receivables
    elif accounts_receivable is not None:
        receivables = accounts_receivable + (vendor_nontrade if vendor_nontrade is not None else 0.0)
    else:
        receivables = None
    inventory = get_row_value(balance_sheet, ["Inventory"], col)

    total_debt = get_row_value(balance_sheet, ["Total Debt"], col)
    if total_debt is None:
        current_debt = get_row_value(balance_sheet, ["Current Debt", "Current Debt And Capital Lease Obligation"], col)
        long_term_debt = get_row_value(balance_sheet, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"], col)
        if current_debt is not None and long_term_debt is not None:
            total_debt = current_debt + long_term_debt
    stockholder_equity = get_row_value(balance_sheet, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"], col)
    stockholder_equity_prev = get_row_value(balance_sheet, ["Stockholders Equity", "Total Stockholder Equity"], col + 1)
    
    avg_stockholder_equity = (
        (stockholder_equity + stockholder_equity_prev) / 2.0
        if stockholder_equity is not None and stockholder_equity_prev is not None
        else None
    )

    # Market Parameters
    market_cap = info.get("marketCap")
    share_price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
    eps_ttm = info.get("epsTrailingTwelveMonths")
    
    # Valuation Multiples
    pe_ratio = None
    if share_price is not None and eps_ttm is not None:
        if eps_ttm > 0:
            pe_ratio = share_price / eps_ttm
        else:
            pe_ratio = None # Marked N/M (Not Meaningful) for loss-making companies

    enterprise_value_std = (
        market_cap + total_debt - cash_and_short_term
        if market_cap is not None and total_debt is not None and cash_and_short_term is not None
        else None
    )
    
    ev_ebitda_std = None
    if enterprise_value_std is not None and ebitda is not None and ebitda > 0:
        ev_ebitda_std = enterprise_value_std / ebitda

    # Ratio Calculations (Full Float Precision or None)
    current_ratio = (current_assets / current_liabilities) if (current_assets is not None and current_liabilities is not None and current_liabilities > 0) else None
    
    strict_quick_assets = (
        cash_and_short_term + receivables
        if cash_and_short_term is not None and receivables is not None
        else None
    )
    quick_ratio = (
        strict_quick_assets / current_liabilities
        if strict_quick_assets is not None and current_liabilities is not None and current_liabilities > 0
        else None
    )

    # Debt-to-Equity: Not Meaningful if equity <= 0
    debt_to_equity = None
    if total_debt is not None and stockholder_equity is not None and stockholder_equity > 0:
        debt_to_equity = total_debt / stockholder_equity

    gross_margin = (gross_profit / revenue) if (gross_profit is not None and revenue is not None and revenue > 0) else None
    net_margin = (net_income / revenue) if (net_income is not None and revenue is not None and revenue > 0) else None

    # ROE: Not Meaningful if avg_equity <= 0
    roe = None
    if net_income is not None and avg_stockholder_equity is not None and avg_stockholder_equity > 0:
        roe = net_income / avg_stockholder_equity

    roa = (net_income / avg_total_assets) if (net_income is not None and avg_total_assets is not None and avg_total_assets > 0) else None
    asset_turnover = (revenue / avg_total_assets) if (revenue is not None and avg_total_assets is not None and avg_total_assets > 0) else None

    ratios = {
        "current_ratio": current_ratio,
        "quick_ratio": quick_ratio,
        "debt_to_equity": debt_to_equity,
        "gross_margin": gross_margin,
        "net_margin": net_margin,
        "roe": roe,
        "roa": roa,
        "asset_turnover": asset_turnover,
        "pe_ratio": pe_ratio,
        "ev_ebitda": ev_ebitda_std,
    }

    # Evaluate Benchmarks and Calculate Deterministic Score
    health_evaluation = evaluate_financial_health(ratios, is_financial_sector=is_financial_sector, eps_ttm=eps_ttm, equity=stockholder_equity)

    return {
        "symbol": symbol,
        "is_financial_sector": is_financial_sector,
        "ratios": ratios,
        "health_score": health_evaluation["score"],
        "health_status": health_evaluation["status"],
        "ratio_evaluations": health_evaluation["evaluations"],
        "ev_breakdown": {
            "market_cap": market_cap,
            "share_price": share_price,
            "eps_ttm": eps_ttm,
            "total_debt": total_debt,
            "cash_and_short_term": cash_and_short_term,
            "enterprise_value_std": enterprise_value_std,
            "operating_income": operating_income,
            "depreciation_amortization": depreciation_amortization,
            "ebitda": ebitda,
            "ebitda_method": ebitda_method,
            "ev_ebitda_std": ev_ebitda_std,
            "market_data_as_of": info.get("market_data_as_of"),
            "market_data_provider": info.get("market_data_provider"),
            "statement_data_provider": info.get("statement_data_provider")
        },
        "raw_financials": {
            "revenue": revenue,
            "gross_profit": gross_profit,
            "net_income": net_income,
            "operating_income": operating_income,
            "depreciation_amortization": depreciation_amortization,
            "total_assets": total_assets,
            "total_debt": total_debt,
            "stockholder_equity": stockholder_equity,
            "cash_and_equiv": cash_and_equiv,
            "cash_and_short_term": cash_and_short_term,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "inventory": inventory
        }
    }

def evaluate_financial_health(ratios: Dict[str, Optional[float]], is_financial_sector: bool = False, eps_ttm: Optional[float] = None, equity: Optional[float] = None) -> Dict[str, Any]:
    """
    Evaluates 10 financial ratios using continuous benchmark logic with zero gaps and explicit weights.
    Healthy (1.0), Caution (0.6), Warning (0.2).
    Non-applicable or Not Meaningful (N/A, N/M) ratios carry 0 weight and are excluded from denominator sum.
    """
    evaluations = {}
    total_weighted_points = 0.0
    total_applicable_weight = 0.0

    def add_eval(key: str, name: str, category: str, value: Optional[float], status: str, target: str, fmt: str, pts: float, weight: float):
        nonlocal total_weighted_points, total_applicable_weight
        w_pts = pts * (weight * 100) if status in ["Healthy", "Caution", "Warning"] else 0.0
        
        evaluations[key] = {
            "name": name,
            "category": category,
            "value": value,
            "status": status,
            "target": target,
            "format": fmt,
            "pts": pts,
            "weight": weight,
            "w_pts": w_pts
        }
        
        if status in ["Healthy", "Caution", "Warning"]:
            total_weighted_points += w_pts
            total_applicable_weight += weight

    # 1. Current Ratio (Liquidity)
    if is_financial_sector:
        add_eval("current_ratio", "Current Ratio", "Liquidity", None, "N/A", "N/A (Financial Sector Balance Sheet)", "{:.2f}", 0.0, 0.0)
    else:
        cr = ratios.get("current_ratio")
        if cr is not None and not np.isnan(cr):
            if cr >= 1.50: st = "Healthy"; pts = 1.0
            elif cr >= 1.00: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            add_eval("current_ratio", "Current Ratio", "Liquidity", cr, st, "Healthy ≥ 1.50 | Caution 1.00–1.49 | Warning < 1.00", "{:.2f}", pts, 0.10)
        else:
            add_eval("current_ratio", "Current Ratio", "Liquidity", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # 2. Strict Quick Ratio (Liquidity)
    if is_financial_sector:
        add_eval("quick_ratio", "Strict Quick Ratio", "Liquidity", None, "N/A", "N/A (Financial Sector Balance Sheet)", "{:.2f}", 0.0, 0.0)
    else:
        qr = ratios.get("quick_ratio")
        if qr is not None and not np.isnan(qr):
            if qr >= 1.00: st = "Healthy"; pts = 1.0
            elif qr >= 0.80: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            add_eval("quick_ratio", "Strict Quick Ratio", "Liquidity", qr, st, "Healthy ≥ 1.00 | Caution 0.80–0.99 | Warning < 0.80", "{:.2f}", pts, 0.10)
        else:
            add_eval("quick_ratio", "Strict Quick Ratio", "Liquidity", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # 3. Debt to Equity (Leverage)
    de = ratios.get("debt_to_equity")
    if equity is not None and equity <= 0:
        add_eval("debt_to_equity", "Debt-to-Equity", "Leverage", None, "N/M", "Not Meaningful (Negative Equity)", "{:.2f}", 0.0, 0.0)
    elif de is not None and not np.isnan(de):
        target_str = "Healthy ≤ 1.50 | Caution 1.51–2.00 | Warning > 2.00"
        if is_financial_sector:
            if de <= 3.50: st = "Healthy"; pts = 1.0
            elif de <= 5.00: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            target_str = "Healthy ≤ 3.50 | Caution 3.51–5.00 | Warning > 5.00 (Financial Sector)"
        else:
            if de <= 1.50: st = "Healthy"; pts = 1.0
            elif de <= 2.00: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
        add_eval("debt_to_equity", "Debt-to-Equity", "Leverage", de, st, target_str, "{:.2f}", pts, 0.10)
    else:
        add_eval("debt_to_equity", "Debt-to-Equity", "Leverage", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # 4. Gross Margin (Profitability)
    if is_financial_sector:
        add_eval("gross_margin", "Gross Margin", "Profitability", None, "N/A", "N/A (Financial Sector Operations)", "{:.1%}", 0.0, 0.0)
    else:
        gm = ratios.get("gross_margin")
        if gm is not None and not np.isnan(gm):
            if gm >= 0.40: st = "Healthy"; pts = 1.0
            elif gm >= 0.20: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            add_eval("gross_margin", "Gross Margin", "Profitability", gm, st, "Healthy ≥ 40% | Caution 20%–39.9% | Warning < 20%", "{:.1%}", pts, 0.10)
        else:
            add_eval("gross_margin", "Gross Margin", "Profitability", None, "N/A", "Data Unavailable", "{:.1%}", 0.0, 0.0)

    # 5. Net Margin (Profitability)
    nm = ratios.get("net_margin")
    if nm is not None and not np.isnan(nm):
        if nm >= 0.15: st = "Healthy"; pts = 1.0
        elif nm >= 0.05: st = "Caution"; pts = 0.6
        else: st = "Warning"; pts = 0.2
        add_eval("net_margin", "Net Margin", "Profitability", nm, st, "Healthy ≥ 15% | Caution 5%–14.9% | Warning < 5%", "{:.1%}", pts, 0.10)
    else:
        add_eval("net_margin", "Net Margin", "Profitability", None, "N/A", "Data Unavailable", "{:.1%}", 0.0, 0.0)

    # 6. Standard ROE (Profitability)
    roe = ratios.get("roe")
    if equity is not None and equity <= 0:
        add_eval("roe", "Return on Equity (ROE)", "Profitability", None, "N/M", "Not Meaningful (Negative Equity)", "{:.1%}", 0.0, 0.0)
    elif roe is not None and not np.isnan(roe):
        if roe >= 0.15: st = "Healthy"; pts = 1.0
        elif roe >= 0.08: st = "Caution"; pts = 0.6
        else: st = "Warning"; pts = 0.2
        add_eval("roe", "Return on Equity (ROE)", "Profitability", roe, st, "Healthy ≥ 15% | Caution 8%–14.9% | Warning < 8%", "{:.1%}", pts, 0.10)
    else:
        add_eval("roe", "Return on Equity (ROE)", "Profitability", None, "N/A", "Data Unavailable", "{:.1%}", 0.0, 0.0)

    # 7. Standard ROA (Profitability)
    roa = ratios.get("roa")
    if roa is not None and not np.isnan(roa):
        target_str = "Healthy ≥ 8% | Caution 3%–7.9% | Warning < 3%"
        if is_financial_sector:
            if roa >= 0.015: st = "Healthy"; pts = 1.0
            elif roa >= 0.008: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            target_str = "Healthy ≥ 1.5% | Caution 0.8%–1.49% | Warning < 0.8% (Bank ROA Target)"
        else:
            if roa >= 0.08: st = "Healthy"; pts = 1.0
            elif roa >= 0.03: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
        add_eval("roa", "Return on Assets (ROA)", "Profitability", roa, st, target_str, "{:.1%}", pts, 0.10)
    else:
        add_eval("roa", "Return on Assets (ROA)", "Profitability", None, "N/A", "Data Unavailable", "{:.1%}", 0.0, 0.0)

    # 8. Standard Asset Turnover (Efficiency)
    at = ratios.get("asset_turnover")
    if at is not None and not np.isnan(at):
        target_str = "Healthy ≥ 0.75 | Caution 0.40–0.74 | Warning < 0.40"
        if is_financial_sector:
            if at >= 0.05: st = "Healthy"; pts = 1.0
            elif at >= 0.02: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            target_str = "Healthy ≥ 0.05 | Caution 0.02–0.04 | Warning < 0.02 (Financial Institution Asset Yield)"
        else:
            if at >= 0.75: st = "Healthy"; pts = 1.0
            elif at >= 0.40: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
        add_eval("asset_turnover", "Asset Turnover", "Efficiency", at, st, target_str, "{:.2f}", pts, 0.10)
    else:
        add_eval("asset_turnover", "Asset Turnover", "Efficiency", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # 9. TTM P/E Ratio (Valuation)
    pe = ratios.get("pe_ratio")
    if eps_ttm is not None and eps_ttm <= 0:
        add_eval("pe_ratio", "TTM P/E Ratio", "Valuation", None, "N/M", "Not Meaningful (Negative EPS)", "{:.2f}", 0.0, 0.0)
    elif pe is not None and not np.isnan(pe):
        if 0 < pe <= 25.0: st = "Healthy"; pts = 1.0
        elif pe <= 40.0: st = "Caution"; pts = 0.6
        else: st = "Warning"; pts = 0.2
        add_eval("pe_ratio", "TTM P/E Ratio", "Valuation", pe, st, "Healthy ≤ 25.0 | Caution 25.1–40.0 | Warning > 40.0", "{:.2f}", pts, 0.10)
    else:
        add_eval("pe_ratio", "TTM P/E Ratio", "Valuation", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # 10. Standard EV/EBITDA (Valuation)
    if is_financial_sector:
        add_eval("ev_ebitda", "EV/EBITDA", "Valuation", None, "N/A", "N/A (Financial Sector Valuation)", "{:.2f}", 0.0, 0.0)
    else:
        eve = ratios.get("ev_ebitda")
        if eve is not None and not np.isnan(eve):
            if 0 < eve <= 15.0: st = "Healthy"; pts = 1.0
            elif eve <= 25.0: st = "Caution"; pts = 0.6
            else: st = "Warning"; pts = 0.2
            add_eval("ev_ebitda", "EV/EBITDA", "Valuation", eve, st, "Healthy ≤ 15.0 | Caution 15.1–25.0 | Warning > 25.0", "{:.2f}", pts, 0.10)
        else:
            add_eval("ev_ebitda", "EV/EBITDA", "Valuation", None, "N/A", "Data Unavailable", "{:.2f}", 0.0, 0.0)

    # Calculate final normalized score
    if total_applicable_weight > 0:
        max_possible_points = total_applicable_weight * 100.0
        final_score = int(round((total_weighted_points / max_possible_points) * 100.0))
    else:
        final_score = None

    if final_score is None:
        overall_status = "Insufficient Data"
    elif final_score >= 80:
        overall_status = "Strong Financial Health & Valuation"
    elif final_score >= 60:
        overall_status = "Moderate Financial Health & Valuation"
    else:
        overall_status = "Weak Financial Health & Valuation"

    return {
        "score": final_score,
        "status": overall_status,
        "evaluations": evaluations
    }
