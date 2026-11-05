"""Assumption-driven operating-company forecasts. Reported inputs are never overwritten."""
from __future__ import annotations

import calendar
import hashlib
import json
import math
from datetime import date

import pandas as pd

VERSION = "2026.11.04-dcf-1"
MODEL_SCOPE = ("Five annual periods from the latest coherent reported period. End-year FCFF discounting at user-entered WACC. "
    "Terminal reinvestment equals terminal growth divided by terminal ROIC. No automatic financing plug. "
    "Other noncash assets change only by capex less D&A; other liabilities are held constant. "
    "Operating margins include stock compensation, treated as an economic cost in DCF. "
    "Cash taxes equal positive pretax income times the selected rate, without NOLs or deferred-tax schedules. "
    "Interest uses average opening/closing borrowing balances. No acquisitions, disposals, OCI, FX or minority-interest forecasts.")
SOURCES = (
    "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/definitions.html",
    "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/termvalueexreturns.htm",
)
FIELDS = {
    "revenue": ("income_stmt", ("Total Revenue", "Operating Revenue", "Revenue")),
    "gross_profit": ("income_stmt", ("Gross Profit",)),
    "operating_income": ("income_stmt", ("Operating Income",)),
    "net_income": ("income_stmt", ("Net Income", "Net Income Common Stockholders")),
    "pretax_income": ("income_stmt", ("Pretax Income",)),
    "tax_provision": ("income_stmt", ("Tax Provision",)),
    "interest_expense": ("income_stmt", ("Interest Expense", "Interest Expense Non Operating")),
    "assets": ("balance_sheet", ("Total Assets",)),
    "liabilities": ("balance_sheet", ("Total Liabilities Net Minority Interest",)),
    "equity": ("balance_sheet", ("Stockholders Equity", "Common Stock Equity")),
    "cash": ("balance_sheet", ("Cash And Cash Equivalents",)),
    "receivables": ("balance_sheet", ("Accounts Receivable",)),
    "inventory": ("balance_sheet", ("Inventory",)),
    "payables": ("balance_sheet", ("Accounts Payable",)),
    "debt": ("balance_sheet", ("Total Debt",)),
    "shares": ("balance_sheet", ("Ordinary Shares Number",)),
    "operating_cash_flow": ("cash_flow", ("Operating Cash Flow",)),
    "capital_expenditure": ("cash_flow", ("Capital Expenditure", "Capital Expenditures")),
    "da": ("cash_flow", ("Depreciation And Amortization", "Depreciation Depletion And Amortization")),
    "sbc": ("cash_flow", ("Stock Based Compensation",)),
    "investing_cash_flow": ("cash_flow", ("Investing Cash Flow",)),
    "financing_cash_flow": ("cash_flow", ("Financing Cash Flow",)),
}
DRIVERS = ("revenue_growth", "gross_margin", "operating_margin", "tax_rate", "capex_rate", "da_rate", "sbc_rate",
           "receivables_days", "inventory_days", "payables_days", "interest_rate", "debt_draw", "debt_repayment",
           "equity_issuance", "dividends", "buybacks")
NONNEGATIVE = set(DRIVERS) - {"revenue_growth", "gross_margin", "operating_margin"}
OPENING = ("revenue", "assets", "liabilities", "equity", "cash", "receivables", "inventory", "payables", "debt")


class ModelUnavailable(ValueError):
    pass


def number(value):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _period(frame):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    return max(pd.Timestamp(c).date() for c in frame.columns)


def _row(frame, aliases, period):
    if not isinstance(frame, pd.DataFrame) or frame.empty or period is None:
        return None, None
    columns = [c for c in frame.columns if pd.Timestamp(c).date() == period]
    if len(columns) != 1:
        return None, None
    matches = {str(i).strip().casefold(): i for i in frame.index}
    for alias in aliases:
        if alias.casefold() in matches:
            name = matches[alias.casefold()]
            value = number(frame.loc[name, columns[0]])
            if value is not None:
                return value, str(name)
    return None, None


def build_baseline(stock, metrics):
    analysis_keys=('income_stmt','balance_sheet','cash_flow')
    use_latest=any(isinstance(stock.get('analysis_'+key),pd.DataFrame) and not stock['analysis_'+key].empty for key in analysis_keys)
    basis=stock.get('analysis_basis') or {}
    if use_latest:
        stock={**stock,**{key:stock.get('analysis_'+key,pd.DataFrame()) for key in analysis_keys}}
    flow_basis=basis.get('income') if use_latest else 'latest_annual'
    cash_basis=basis.get('cash_flow') if use_latest else 'latest_annual'
    balance_basis=basis.get('balance_sheet') if use_latest else 'latest_annual'
    info = stock.get("info") or {}
    period = _period(stock.get("income_stmt"))
    profile = (metrics.get("applicability_profile") or {}).get("key")
    missing = []
    valid_flows={'latest_annual','latest_annual_fallback','trailing_twelve_months'}
    if flow_basis not in valid_flows or cash_basis not in valid_flows:
        missing.append('A complete annual or trailing-twelve-month income and cash-flow basis is required')
    if stock.get("integrity_hold_reason"):
        missing.append(stock["integrity_hold_reason"])
    if profile not in {"operating_company", "regulated_utility"}:
        missing.append("This operating-company DCF does not support an unverified company type, financial institution or REIT.")
    if not (info.get("financialCurrency") or info.get("currency")):
        missing.append("Reporting currency is unavailable")
    if period is None:
        missing.append("Reported annual or trailing-twelve-month income statement is unavailable")
    elif period > date.today():
        missing.append("The annual reporting period is in the future")
    for name in ("balance_sheet", "cash_flow"):
        if _period(stock.get(name)) != period or period is None:
            missing.append(f"The latest {name.replace('_', ' ')} does not match the annual/TTM income statement date")
    values, provenance = {}, {}
    for key, (table, aliases) in FIELDS.items():
        value, row = _row(stock.get(table), aliases, period)
        values[key] = value
        provenance[key] = {"statement": table, "row": row, "period": period.isoformat() if period else None,
                           "provider": info.get("statement_data_provider")}
    # Some providers expose only the total receivable balance. It is usable as
    # its own broader working-capital bucket, with its original row disclosed.
    if values["receivables"] is None:
        values["receivables"], row = _row(stock.get("balance_sheet"), ("Receivables",), period)
        provenance["receivables"]["row"] = row
    if info.get("statement_data_provider") != "SEC Company Facts":
        current_debt, current_row = _row(stock.get("balance_sheet"), ("Current Debt",), period)
        long_debt, long_row = _row(stock.get("balance_sheet"), ("Long Term Debt",), period)
        values["debt"] = current_debt + long_debt if current_debt is not None and long_debt is not None else None
        provenance["debt"]["row"] = f"{current_row} + {long_row}" if values["debt"] is not None else None
        provenance["debt"]["definition"] = "Borrowings from explicit debt rows; aggregate lease/debt rows are not substituted."
    for key in OPENING:
        if values[key] is None:
            missing.append("Missing reported opening input: " + key.replace("_", " "))
    if values["revenue"] is not None and values["revenue"] <= 0:
        missing.append("A revenue-driven operating model requires positive reported revenue")
    for key in ("assets", "liabilities", "cash", "receivables", "inventory", "payables", "debt"):
        if values[key] is not None and values[key] < 0:
            missing.append("Negative opening input requires a specialist model: " + key)
    if all(values[k] is not None for k in ("assets", "liabilities", "equity")):
        difference = values["assets"] - values["liabilities"] - values["equity"]
        if abs(difference) > 1:
            missing.append("Reported assets do not reconcile to liabilities plus parent equity within one currency unit. Minority interests or rounding require a more detailed model.")
    v = values
    if all(v[k] is not None for k in ("assets", "cash", "receivables", "inventory")):
        v["other_noncash_assets"] = v["assets"] - v["cash"] - v["receivables"] - v["inventory"]
        if v["other_noncash_assets"] < -1:
            missing.append("Cash and working-capital asset inputs exceed reported assets")
    if all(v[k] is not None for k in ("liabilities", "debt", "payables")):
        v["other_liabilities"] = v["liabilities"] - v["debt"] - v["payables"]
        if v["other_liabilities"] < -1:
            missing.append("Borrowings and payables exceed reported liabilities")
    historic = {key: None for key in DRIVERS}
    if v["revenue"] and v["revenue"] > 0:
        for key, source in (("gross_margin", "gross_profit"), ("operating_margin", "operating_income"),
                            ("da_rate", "da"), ("sbc_rate", "sbc")):
            if v[source] is not None:
                historic[key] = v[source] / v["revenue"]
        if v["capital_expenditure"] is not None and v["capital_expenditure"] <= 0:
            historic["capex_rate"] = -v["capital_expenditure"] / v["revenue"]
        if v["receivables"] is not None:
            historic["receivables_days"] = 365 * v["receivables"] / v["revenue"]
        cogs = v["revenue"] - v["gross_profit"] if v["gross_profit"] is not None else None
        if cogs and cogs > 0:
            for driver, source in (("inventory_days", "inventory"), ("payables_days", "payables")):
                if v[source] is not None:
                    historic[driver] = 365 * v[source] / cogs
    if v["pretax_income"] and v["pretax_income"] > 0 and v["tax_provision"] is not None:
        rate = v["tax_provision"] / v["pretax_income"]
        if 0 <= rate <= 1:
            historic["tax_rate"] = rate
    v['prior_revenue'] = v['prior_debt'] = None
    if period:
        prior_income = [pd.Timestamp(c).date() for c in stock.get("income_stmt", pd.DataFrame()).columns if 350 <= (period-pd.Timestamp(c).date()).days<=380]
        prior_balance = [pd.Timestamp(c).date() for c in stock.get("balance_sheet", pd.DataFrame()).columns if 350 <= (period-pd.Timestamp(c).date()).days<=380]
        if len(prior_income)==1:
            prior_revenue, row = _row(stock.get("income_stmt"), FIELDS["revenue"][1], prior_income[0])
            v['prior_revenue']=prior_revenue
            provenance['prior_revenue']={'statement':'income_stmt','row':row,'period':prior_income[0].isoformat(),'provider':info.get('statement_data_provider')}
            if prior_revenue and prior_revenue>0 and v['revenue'] is not None:
                historic['revenue_growth']=v['revenue']/prior_revenue-1
        if len(prior_balance)==1:
            prior_debt, row = _row(stock.get("balance_sheet"), FIELDS["debt"][1], prior_balance[0])
            if info.get("statement_data_provider") != "SEC Company Facts":
                prior_current, _ = _row(stock.get("balance_sheet"), ("Current Debt",), prior_balance[0])
                prior_long, _ = _row(stock.get("balance_sheet"), ("Long Term Debt",), prior_balance[0])
                prior_debt = prior_current + prior_long if prior_current is not None and prior_long is not None else None
                row='Current Debt + Long Term Debt'
            v['prior_debt']=prior_debt
            provenance['prior_debt']={'statement':'balance_sheet','row':row,'period':prior_balance[0].isoformat(),'provider':info.get('statement_data_provider')}
            if prior_debt is not None and v["debt"] is not None and prior_debt + v["debt"] > 0 and v["interest_expense"] is not None and v["interest_expense"] >= 0:
                historic["interest_rate"] = v["interest_expense"] / ((prior_debt + v["debt"]) / 2)
    filing = stock.get("sec_filing") or {}
    source_records = (stock.get("sec_statement_import") or {}).get("provenance") or {}
    prefixes={'income_stmt':'ttm_income' if flow_basis=='trailing_twelve_months' else 'annual_income',
        'cash_flow':'ttm_cash_flow' if cash_basis=='trailing_twelve_months' else 'annual_cash_flow',
        'balance_sheet':'quarterly_balance' if balance_basis=='latest_quarter' else 'annual_balance'}
    chosen_records = {key: value for key, value in source_records.items() if period and key.split(':')[0] in set(prefixes.values()) and key.endswith(period.isoformat())}
    for key in ('prior_revenue','prior_debt'):
        provenance.setdefault(key, {'statement':'income_stmt' if key=='prior_revenue' else 'balance_sheet','row':None,'period':None,'provider':info.get('statement_data_provider')})
    for key, item in provenance.items():
        prefix = prefixes[item['statement']]
        item['basis']=flow_basis if item['statement']=='income_stmt' else cash_basis if item['statement']=='cash_flow' else balance_basis
        record = (source_records.get(f"{prefix}:{item['period']}") or {}).get(item["row"]) or {}
        item["sec_facts"] = record
    result = {"status": "unavailable" if missing else "ready", "missing": missing, "symbol": stock["symbol"],
              "company_name": info.get("longName") or info.get("shortName") or stock["symbol"],
              "period": period.isoformat() if period else None, "currency": info.get("financialCurrency") or info.get("currency"),
              "flow_basis":flow_basis,"cash_flow_basis":cash_basis,"balance_sheet_basis":balance_basis,
              "values": values, "provenance": provenance, "historical_drivers": historic, "scope": MODEL_SCOPE,
              "latest_filing": filing, "model_version": VERSION,
              "statement_provenance": chosen_records}
    result["input_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return result


def _validated_year(raw):
    if set(raw) != set(DRIVERS):
        raise ModelUnavailable("Every year requires all operating and financing assumptions; missing values are not zero")
    out = {key: number(value) for key, value in raw.items()}
    if any(value is None for value in out.values()):
        raise ModelUnavailable("All forecast assumptions must be finite numbers")
    if out["revenue_growth"] <= -1 or out["gross_margin"] > 1 or out["operating_margin"] > out["gross_margin"]:
        raise ModelUnavailable("Growth must exceed -100%; gross margin cannot exceed 100%; operating margin cannot exceed gross margin in this model")
    if not 0 <= out["tax_rate"] <= 1 or any(out[key] < 0 for key in NONNEGATIVE):
        raise ModelUnavailable("Tax must be between 0% and 100%; financing, asset drivers and borrowing costs cannot be negative")
    if out["da_rate"] + out["sbc_rate"] > 1 - out["operating_margin"] + 1e-12:
        raise ModelUnavailable("D&A and stock compensation exceed total modeled operating expenses")
    return out


def run_model(baseline, years, valuation, note):
    if baseline["status"] != "ready":
        raise ModelUnavailable("; ".join(baseline["missing"]))
    if len(years) != 5:
        raise ModelUnavailable("Supply assumptions for all five forecast years")
    if not isinstance(note, str) or not note.strip() or len(note) > 4000:
        raise ModelUnavailable("Record the rationale and scope of your assumptions (up to 4000 characters)")
    years = [_validated_year(value) for value in years]
    required = {"wacc", "terminal_growth", "terminal_roic", "cash_in_bridge", "nonoperating_assets", "other_claims"}
    if set(valuation) != required:
        raise ModelUnavailable("Enter all discount-rate, terminal and equity-bridge assumptions explicitly")
    valuation = {key: number(value) for key, value in valuation.items()}
    if any(value is None for value in valuation.values()):
        raise ModelUnavailable("All valuation assumptions must be finite numbers")
    if valuation["wacc"] <= 0 or valuation["terminal_growth"] <= -1 or valuation["terminal_growth"] >= valuation["wacc"] or valuation["terminal_roic"] <= max(0, valuation["terminal_growth"]):
        raise ModelUnavailable("WACC must be positive and exceed terminal growth. Terminal ROIC must be positive and exceed positive terminal growth")
    if any(valuation[key] < 0 for key in ("cash_in_bridge", "nonoperating_assets", "other_claims")) or valuation["cash_in_bridge"] > baseline["values"]["cash"]:
        raise ModelUnavailable("Bridge amounts cannot be negative; selected cash cannot exceed reported opening cash")
    previous = dict(baseline["values"])
    base_date = date.fromisoformat(baseline["period"])
    forecasts, warnings = [], []
    try:
        for index, inputs in enumerate(years, 1):
            revenue = previous["revenue"] * (1 + inputs["revenue_growth"])
            gross_profit = revenue * inputs["gross_margin"]
            cogs = revenue - gross_profit
            ebit = revenue * inputs["operating_margin"]
            debt = previous["debt"] + inputs["debt_draw"] - inputs["debt_repayment"]
            if debt < 0:
                raise ModelUnavailable(f"Year {index}: repayments exceed available borrowings")
            interest = (previous["debt"] + debt) / 2 * inputs["interest_rate"]
            pretax = ebit - interest
            taxes = max(pretax, 0) * inputs["tax_rate"]
            net_income = pretax - taxes
            da, sbc, capex = (revenue * inputs[key] for key in ("da_rate", "sbc_rate", "capex_rate"))
            receivables = revenue / 365 * inputs["receivables_days"]
            inventory = cogs / 365 * inputs["inventory_days"]
            payables = cogs / 365 * inputs["payables_days"]
            delta_wc = receivables - previous["receivables"] + inventory - previous["inventory"] - payables + previous["payables"]
            cfo = net_income + da + sbc - delta_wc
            cfi = -capex
            cff = inputs["debt_draw"] - inputs["debt_repayment"] + inputs["equity_issuance"] - inputs["dividends"] - inputs["buybacks"]
            cash = previous["cash"] + cfo + cfi + cff
            other_assets = previous["other_noncash_assets"] + capex - da
            if other_assets < -1:
                raise ModelUnavailable(f"Year {index}: modeled D&A exceeds remaining noncash assets and new capex")
            equity = previous["equity"] + net_income + sbc + inputs["equity_issuance"] - inputs["dividends"] - inputs["buybacks"]
            assets = cash + receivables + inventory + other_assets
            liabilities = debt + payables + previous["other_liabilities"]
            nopat = ebit - max(ebit, 0) * inputs["tax_rate"]
            fcff = nopat + da - capex - delta_wc
            end = date(base_date.year + index, base_date.month, min(base_date.day, calendar.monthrange(base_date.year + index, base_date.month)[1]))
            row = {"year": index, "period": end.isoformat(), "revenue": revenue, "cogs": cogs, "gross_profit": gross_profit,
                "operating_expenses": gross_profit - ebit, "operating_income": ebit, "interest_expense": interest,
                "pretax_income": pretax, "tax_provision": taxes, "net_income": net_income, "da": da, "sbc": sbc,
                "capex": capex, "receivables": receivables, "inventory": inventory, "payables": payables,
                "change_working_capital": delta_wc, "operating_cash_flow": cfo, "investing_cash_flow": cfi,
                "financing_cash_flow": cff, "cash": cash, "debt": debt, "other_noncash_assets": other_assets,
                "other_liabilities": previous["other_liabilities"], "assets": assets, "liabilities": liabilities,
                "equity": equity, "nopat": nopat, "fcff": fcff, "discount_factor": (1 + valuation["wacc"]) ** index,
                "funding_gap": max(-cash, 0)}
            row["present_value_fcff"] = fcff / row["discount_factor"]
            row["balance_difference"] = assets - liabilities - equity
            row["cash_difference"] = cash - previous["cash"] - cfo - cfi - cff
            if not all(math.isfinite(value) for value in row.values() if isinstance(value, (float, int))):
                raise ModelUnavailable("Forecast assumptions produced a non-finite result")
            tolerance = max(1, abs(assets) * 1e-12)
            if abs(row["balance_difference"]) > tolerance or abs(row["cash_difference"]) > tolerance:
                raise ModelUnavailable("Forecast cash or balance-sheet reconciliation failed")
            if cash < 0:
                warnings.append(f"Year {index} has a cash funding gap. No borrowing or equity plug has been inserted.")
            forecasts.append(row)
            previous = row
        final = forecasts[-1]
        terminal_nopat = final["nopat"] * (1 + valuation["terminal_growth"])
        reinvestment_rate = valuation["terminal_growth"] / valuation["terminal_roic"]
        terminal_fcff = terminal_nopat * (1 - reinvestment_rate)
        terminal_value = terminal_fcff / (valuation["wacc"] - valuation["terminal_growth"])
        pv_terminal = terminal_value / final["discount_factor"]
        enterprise_value = sum(row["present_value_fcff"] for row in forecasts) + pv_terminal
        equity_value = enterprise_value + valuation["cash_in_bridge"] + valuation["nonoperating_assets"] - baseline["values"]["debt"] - valuation["other_claims"]
        valuation_ok = terminal_fcff > 0 and not warnings
        reason = None if valuation_ok else ("Resolve explicit cash funding gaps before using this going-concern valuation." if warnings else "The terminal year does not generate positive normalized cash flow.")
        dcf = {"status": "ready" if valuation_ok else "unavailable", "reason": reason,
            "terminal_nopat": terminal_nopat, "terminal_reinvestment_rate": reinvestment_rate,
            "terminal_fcff": terminal_fcff, "terminal_value": terminal_value if valuation_ok else None,
            "present_value_terminal": pv_terminal if valuation_ok else None,
            "enterprise_value": enterprise_value if valuation_ok else None,
            "equity_value": equity_value if valuation_ok else None,
            "value_per_share": equity_value / baseline["values"]["shares"] if valuation_ok and equity_value >= 0 and baseline["values"]["shares"] and baseline["values"]["shares"] > 0 else None,
            "per_share_scope": "Uses reported point-in-time common shares at the baseline date. Weighted-average EPS shares are not substituted.",
            "valuation_date": baseline["period"], "discount_timing": "Annual end-year; valuation at the baseline reporting date, not today's market quote date."}
        if not all(value is None or not isinstance(value, (float, int)) or math.isfinite(value) for value in dcf.values()):
            raise ModelUnavailable("Valuation assumptions produced a non-finite result")
    except (OverflowError, ZeroDivisionError) as error:
        raise ModelUnavailable("Assumptions exceed the supported numerical range") from error
    return {"symbol": baseline["symbol"], "baseline": baseline, "assumptions": {"years": years, "valuation": valuation, "note": note.strip()},
            "forecasts": forecasts, "dcf": dcf, "warnings": warnings, "model_version": VERSION,
            "model_code_sha256": hashlib.sha256(__import__("pathlib").Path(__file__).read_bytes()).hexdigest(),
            "methodology_sources": list(SOURCES), "scope": MODEL_SCOPE,
            "actuals_policy": "User assumptions and projections are separate from source actuals and never alter the public financial-health screen."}
