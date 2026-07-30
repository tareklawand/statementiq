import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

def get_row_value(df: pd.DataFrame, posibles_names: list, col_idx: int = 0) -> Optional[float]:
    """Helper to safely extract numerical value from financial dataframe row by matching possible field names."""
    if df is None or df.empty:
        return None
    
    # Lowercase row index for matching
    df_index_lower = [str(idx).strip().lower() for idx in df.index]
    
    for name in posibles_names:
        name_lower = name.strip().lower()
        if name_lower in df_index_lower:
            matched_idx = df_index_lower.index(name_lower)
            try:
                val = df.iloc[matched_idx, col_idx]
                if pd.notna(val):
                    return float(val)
            except Exception:
                continue
    return None

def compute_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes 10 core financial ratios and a deterministic Financial Health Score (0-100).
    Returns ratio values, raw financial values, benchmark statuses, and health score details.
    """
    info = data.get("info", {})
    income_stmt = data.get("income_stmt", pd.DataFrame())
    balance_sheet = data.get("balance_sheet", pd.DataFrame())
    cash_flow = data.get("cash_flow", pd.DataFrame())
    
    # Latest Year Financial items (Column 0 is latest year)
    col = 0
    
    # Financial Statement Values
    revenue = get_row_value(income_stmt, ["Total Revenue", "Operating Revenue", "Revenue"], col)
    gross_profit = get_row_value(income_stmt, ["Gross Profit"], col)
    net_income = get_row_value(income_stmt, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"], col)
    ebitda = get_row_value(income_stmt, ["Normalized EBITDA", "EBITDA", "EBIT"], col)
    
    total_assets = get_row_value(balance_sheet, ["Total Assets"], col)
    current_assets = get_row_value(balance_sheet, ["Current Assets", "Total Current Assets"], col)
    current_liabilities = get_row_value(balance_sheet, ["Current Liabilities", "Total Current Liabilities"], col)
    cash_and_equiv = get_row_value(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"], col)
    short_term_investments = get_row_value(balance_sheet, ["Other Short Term Investments", "Short Term Investments"], col) or 0.0
    receivables = get_row_value(balance_sheet, ["Receivables", "Accounts Receivable", "Net Receivables"], col) or 0.0
    inventory = get_row_value(balance_sheet, ["Inventory", "Total Inventory"], col) or 0.0
    
    total_debt = get_row_value(balance_sheet, ["Total Debt"], col)
    if total_debt is None:
        st_debt = get_row_value(balance_sheet, ["Current Debt", "Current Debt And Capital Lease Obligation", "Short Long Term Debt"], col) or 0.0
        lt_debt = get_row_value(balance_sheet, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"], col) or 0.0
        total_debt = st_debt + lt_debt if (st_debt + lt_debt > 0) else None

    stockholder_equity = get_row_value(balance_sheet, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"], col)
    
    # Ratios Calculation
    # 1. Current Ratio
    if current_assets is not None and current_liabilities and current_liabilities != 0:
        current_ratio = current_assets / current_liabilities
    else:
        current_ratio = info.get("currentRatio")
        
    # 2. Quick Ratio
    if current_assets is not None and inventory is not None and current_liabilities and current_liabilities != 0:
        quick_ratio = (current_assets - inventory) / current_liabilities
    elif cash_and_equiv is not None and current_liabilities and current_liabilities != 0:
        quick_ratio = (cash_and_equiv + short_term_investments + receivables) / current_liabilities
    else:
        quick_ratio = info.get("quickRatio")

    # 3. Debt to Equity
    if total_debt is not None and stockholder_equity and stockholder_equity != 0:
        debt_to_equity = total_debt / stockholder_equity
    else:
        debt_to_equity = info.get("debtToEquity")
        if debt_to_equity is not None and debt_to_equity > 10: # yfinance sometimes reports debtToEquity as percentage (e.g. 150 instead of 1.5)
            debt_to_equity = debt_to_equity / 100.0

    # 4. Gross Margin
    if gross_profit is not None and revenue and revenue != 0:
        gross_margin = gross_profit / revenue
    else:
        gross_margin = info.get("grossMargins")

    # 5. Net Margin
    if net_income is not None and revenue and revenue != 0:
        net_margin = net_income / revenue
    else:
        net_margin = info.get("profitMargins")

    # 6. Return on Equity (ROE)
    if net_income is not None and stockholder_equity and stockholder_equity != 0:
        roe = net_income / stockholder_equity
    else:
        roe = info.get("returnOnEquity")

    # 7. Return on Assets (ROA)
    if net_income is not None and total_assets and total_assets != 0:
        roa = net_income / total_assets
    else:
        roa = info.get("returnOnAssets")

    # 8. Asset Turnover
    if revenue is not None and total_assets and total_assets != 0:
        asset_turnover = revenue / total_assets
    else:
        asset_turnover = None

    # 9. P/E Ratio
    pe_ratio = info.get("trailingPE") or info.get("forwardPE")

    # 10. EV/EBITDA
    ev_ebitda = info.get("enterpriseToEbitda")
    if ev_ebitda is None and ebitda and ebitda > 0:
        ev = info.get("enterpriseValue")
        if ev:
            ev_ebitda = ev / ebitda

    # Compile Ratio Dictionary
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
        "ev_ebitda": ev_ebitda,
    }

    # Evaluate Benchmarks and Calculate Health Score
    health_evaluation = evaluate_financial_health(ratios)

    return {
        "ratios": ratios,
        "health_score": health_evaluation["score"],
        "health_status": health_evaluation["status"],
        "ratio_evaluations": health_evaluation["evaluations"],
        "raw_financials": {
            "revenue": revenue,
            "gross_profit": gross_profit,
            "net_income": net_income,
            "total_assets": total_assets,
            "total_debt": total_debt,
            "stockholder_equity": stockholder_equity,
            "cash_and_equiv": cash_and_equiv,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
        }
    }

def evaluate_financial_health(ratios: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """
    Evaluates each ratio against standard financial benchmarks and calculates a weighted Financial Health Score (0-100).
    """
    evaluations = {}
    total_weight = 0.0
    weighted_score = 0.0

    # Rule definitions: (key, name, weight, healthy_condition_str, scoring_func)
    # Scoring func returns normalized score 0.0 to 1.0, and status 'Healthy', 'Caution', 'Warning'
    
    # 1. Current Ratio (Weight: 10)
    cr = ratios.get("current_ratio")
    if cr is not None and not np.isnan(cr):
        if cr >= 1.5:
            st, sc = "Healthy", 1.0
        elif cr >= 1.0:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["current_ratio"] = {"name": "Current Ratio", "category": "Liquidity", "value": cr, "status": st, "target": "≥ 1.5", "format": "{:.2f}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["current_ratio"] = {"name": "Current Ratio", "category": "Liquidity", "value": None, "status": "N/A", "target": "≥ 1.5", "format": "N/A"}

    # 2. Quick Ratio (Weight: 10)
    qr = ratios.get("quick_ratio")
    if qr is not None and not np.isnan(qr):
        if qr >= 1.0:
            st, sc = "Healthy", 1.0
        elif qr >= 0.7:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["quick_ratio"] = {"name": "Quick Ratio", "category": "Liquidity", "value": qr, "status": st, "target": "≥ 1.0", "format": "{:.2f}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["quick_ratio"] = {"name": "Quick Ratio", "category": "Liquidity", "value": None, "status": "N/A", "target": "≥ 1.0", "format": "N/A"}

    # 3. Debt to Equity (Weight: 15)
    de = ratios.get("debt_to_equity")
    if de is not None and not np.isnan(de):
        if de <= 1.5:
            st, sc = "Healthy", 1.0
        elif de <= 2.5:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["debt_to_equity"] = {"name": "Debt-to-Equity", "category": "Leverage", "value": de, "status": st, "target": "≤ 1.5", "format": "{:.2f}"}
        weighted_score += sc * 15
        total_weight += 15
    else:
        evaluations["debt_to_equity"] = {"name": "Debt-to-Equity", "category": "Leverage", "value": None, "status": "N/A", "target": "≤ 1.5", "format": "N/A"}

    # 4. Gross Margin (Weight: 15)
    gm = ratios.get("gross_margin")
    if gm is not None and not np.isnan(gm):
        if gm >= 0.40:
            st, sc = "Healthy", 1.0
        elif gm >= 0.20:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["gross_margin"] = {"name": "Gross Margin", "category": "Profitability", "value": gm, "status": st, "target": "≥ 40%", "format": "{:.1%}"}
        weighted_score += sc * 15
        total_weight += 15
    else:
        evaluations["gross_margin"] = {"name": "Gross Margin", "category": "Profitability", "value": None, "status": "N/A", "target": "≥ 40%", "format": "N/A"}

    # 5. Net Margin (Weight: 15)
    nm = ratios.get("net_margin")
    if nm is not None and not np.isnan(nm):
        if nm >= 0.15:
            st, sc = "Healthy", 1.0
        elif nm >= 0.05:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["net_margin"] = {"name": "Net Margin", "category": "Profitability", "value": nm, "status": st, "target": "≥ 15%", "format": "{:.1%}"}
        weighted_score += sc * 15
        total_weight += 15
    else:
        evaluations["net_margin"] = {"name": "Net Margin", "category": "Profitability", "value": None, "status": "N/A", "target": "≥ 15%", "format": "N/A"}

    # 6. ROE (Weight: 10)
    roe = ratios.get("roe")
    if roe is not None and not np.isnan(roe):
        if roe >= 0.15:
            st, sc = "Healthy", 1.0
        elif roe >= 0.08:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["roe"] = {"name": "Return on Equity (ROE)", "category": "Profitability", "value": roe, "status": st, "target": "≥ 15%", "format": "{:.1%}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["roe"] = {"name": "Return on Equity (ROE)", "category": "Profitability", "value": None, "status": "N/A", "target": "≥ 15%", "format": "N/A"}

    # 7. ROA (Weight: 10)
    roa = ratios.get("roa")
    if roa is not None and not np.isnan(roa):
        if roa >= 0.08:
            st, sc = "Healthy", 1.0
        elif roa >= 0.03:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["roa"] = {"name": "Return on Assets (ROA)", "category": "Profitability", "value": roa, "status": st, "target": "≥ 8%", "format": "{:.1%}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["roa"] = {"name": "Return on Assets (ROA)", "category": "Profitability", "value": None, "status": "N/A", "target": "≥ 8%", "format": "N/A"}

    # 8. Asset Turnover (Weight: 10)
    at = ratios.get("asset_turnover")
    if at is not None and not np.isnan(at):
        if at >= 0.75:
            st, sc = "Healthy", 1.0
        elif at >= 0.40:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.2
        evaluations["asset_turnover"] = {"name": "Asset Turnover", "category": "Efficiency", "value": at, "status": st, "target": "≥ 0.75", "format": "{:.2f}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["asset_turnover"] = {"name": "Asset Turnover", "category": "Efficiency", "value": None, "status": "N/A", "target": "≥ 0.75", "format": "N/A"}

    # 9. P/E Ratio (Weight: 10)
    pe = ratios.get("pe_ratio")
    if pe is not None and not np.isnan(pe):
        if 0 < pe <= 25:
            st, sc = "Healthy", 1.0
        elif pe <= 40:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.3
        evaluations["pe_ratio"] = {"name": "P/E Ratio", "category": "Valuation", "value": pe, "status": st, "target": "≤ 25", "format": "{:.2f}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["pe_ratio"] = {"name": "P/E Ratio", "category": "Valuation", "value": None, "status": "N/A", "target": "≤ 25", "format": "N/A"}

    # 10. EV/EBITDA (Weight: 10)
    eve = ratios.get("ev_ebitda")
    if eve is not None and not np.isnan(eve):
        if 0 < eve <= 15:
            st, sc = "Healthy", 1.0
        elif eve <= 25:
            st, sc = "Caution", 0.6
        else:
            st, sc = "Warning", 0.3
        evaluations["ev_ebitda"] = {"name": "EV/EBITDA", "category": "Valuation", "value": eve, "status": st, "target": "≤ 15", "format": "{:.2f}"}
        weighted_score += sc * 10
        total_weight += 10
    else:
        evaluations["ev_ebitda"] = {"name": "EV/EBITDA", "category": "Valuation", "value": None, "status": "N/A", "target": "≤ 15", "format": "N/A"}

    # Final Score normalized out of 100
    if total_weight > 0:
        final_score = int(round((weighted_score / total_weight) * 100))
    else:
        final_score = 50

    if final_score >= 80:
        overall_status = "Strong Financial Health"
    elif final_score >= 60:
        overall_status = "Moderate Financial Health"
    else:
        overall_status = "Weak Financial Health"

    return {
        "score": final_score,
        "status": overall_status,
        "evaluations": evaluations
    }
