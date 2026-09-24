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
    
    # Only actual financial institutions use the institution-specific model.
    # Payment networks (for example Visa and Mastercard) remain in the standard
    # corporate model even though their broad market sector is Financial Services.
    industry = str(info.get("industry") or "").lower()
    is_financial_sector = (
        data.get("is_financial_sector", False) or
        any(kw in industry for kw in [
            "bank", "insurance", "capital markets", "financial conglomerate",
            "financial - conglomerate", "mortgage finance", "asset management",
            "credit services - banks", "savings & loan", "credit union",
        ])
    )

    income_stmt = data.get("analysis_income_stmt", data.get("income_stmt", pd.DataFrame()))
    balance_sheet = data.get("analysis_balance_sheet", data.get("balance_sheet", pd.DataFrame()))
    cash_flow = data.get("analysis_cash_flow", data.get("cash_flow", pd.DataFrame()))
    analysis_basis = data.get("analysis_basis") or {}
    
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
    
    # For TTM returns, compare the latest quarter-end balance with the same
    # quarter one year earlier. Annual fallback compares consecutive year ends.
    if analysis_basis.get("balance_sheet") == "latest_quarter":
        previous_balance_col = 4 if balance_sheet.shape[1] >= 5 else None
    else:
        previous_balance_col = 1 if balance_sheet.shape[1] >= 2 else None
    total_assets = get_row_value(balance_sheet, ["Total Assets"], col)
    total_assets_prev = (
        get_row_value(balance_sheet, ["Total Assets"], previous_balance_col)
        if previous_balance_col is not None else None
    )
    
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
    stockholder_equity_prev = (
        get_row_value(
            balance_sheet,
            ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"],
            previous_balance_col,
        )
        if previous_balance_col is not None else None
    )
    
    avg_stockholder_equity = (
        (stockholder_equity + stockholder_equity_prev) / 2.0
        if stockholder_equity is not None and stockholder_equity_prev is not None
        else None
    )

    # Market Parameters
    share_price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
    reported_market_cap = info.get("marketCap")
    share_count = info.get("impliedSharesOutstanding") or info.get("sharesOutstanding")
    if reported_market_cap is not None:
        market_cap = reported_market_cap
        market_cap_method = "provider_reported"
    elif share_price is not None and share_count is not None and share_price > 0 and share_count > 0:
        market_cap = share_price * share_count
        market_cap_method = "current_price_times_provider_share_count"
    else:
        market_cap = None
        market_cap_method = None
    eps_ttm = info.get("epsTrailingTwelveMonths")
    if eps_ttm is None:
        eps_ttm = get_row_value(income_stmt, ["Diluted EPS", "Diluted EPS Continuing Operations"], col)
    market_currency = info.get("currency")
    statement_currency = info.get("financialCurrency") or market_currency
    currencies_compatible = (
        not market_currency or
        not statement_currency or
        str(market_currency).upper() == str(statement_currency).upper()
    )
    
    # Valuation Multiples
    pe_ratio = None
    if share_price is not None and eps_ttm is not None:
        if eps_ttm > 0:
            pe_ratio = share_price / eps_ttm
        else:
            pe_ratio = None # Marked N/M (Not Meaningful) for loss-making companies

    enterprise_value_std = None
    if not is_financial_sector and currencies_compatible:
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
    operating_margin = (operating_income / revenue) if (operating_income is not None and revenue is not None and revenue > 0) else None
    net_margin = (net_income / revenue) if (net_income is not None and revenue is not None and revenue > 0) else None

    # ROE: Not Meaningful if avg_equity <= 0
    roe = None
    if net_income is not None and avg_stockholder_equity is not None and avg_stockholder_equity > 0:
        roe = net_income / avg_stockholder_equity

    roa = (net_income / avg_total_assets) if (net_income is not None and avg_total_assets is not None and avg_total_assets > 0) else None
    asset_turnover = (revenue / avg_total_assets) if (revenue is not None and avg_total_assets is not None and avg_total_assets > 0) else None

    operating_cash_flow = get_row_value(cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"], col)
    capital_expenditure = get_row_value(cash_flow, ["Capital Expenditure", "Capital Expenditures"], col)
    reported_free_cash_flow = get_row_value(cash_flow, ["Free Cash Flow"], col)
    if reported_free_cash_flow is not None:
        free_cash_flow = reported_free_cash_flow
        free_cash_flow_method = "reported"
    elif operating_cash_flow is not None and capital_expenditure is not None:
        # Normalize provider sign conventions: capex may be a negative outflow
        # or a positive amount spent.
        free_cash_flow = (
            operating_cash_flow + capital_expenditure
            if capital_expenditure < 0
            else operating_cash_flow - capital_expenditure
        )
        free_cash_flow_method = "operating_cash_flow_less_capital_spending"
    else:
        free_cash_flow = None
        free_cash_flow_method = None

    interest_expense = get_row_value(
        income_stmt,
        ["Interest Expense", "Interest Expense Non Operating", "Net Non Operating Interest Income Expense"],
        col,
    )
    interest_coverage = None
    if operating_income is not None and interest_expense is not None and abs(interest_expense) > 0:
        interest_coverage = operating_income / abs(interest_expense)

    debt_to_ebitda = (
        total_debt / ebitda
        if total_debt is not None and ebitda is not None and ebitda > 0
        else None
    )
    net_debt = (
        total_debt - cash_and_short_term
        if total_debt is not None and cash_and_short_term is not None
        else None
    )
    net_debt_to_ebitda = (
        net_debt / ebitda
        if net_debt is not None and ebitda is not None and ebitda > 0
        else None
    )
    working_capital = (
        current_assets - current_liabilities
        if current_assets is not None and current_liabilities is not None
        else None
    )
    free_cash_flow_margin = (
        free_cash_flow / revenue
        if free_cash_flow is not None and revenue is not None and revenue > 0
        else None
    )
    cash_conversion = (
        operating_cash_flow / net_income
        if operating_cash_flow is not None and net_income is not None and net_income > 0
        else None
    )
    free_cash_flow_yield = (
        free_cash_flow / market_cap
        if currencies_compatible and free_cash_flow is not None and market_cap is not None and market_cap > 0
        else None
    )
    cash_ratio = (
        cash_and_short_term / current_liabilities
        if cash_and_short_term is not None and current_liabilities is not None and current_liabilities > 0
        else None
    )

    # Operating cash flow, EBITDA leverage, and interest coverage do not carry
    # the same interpretation for deposit-taking banks and insurers because
    # financing flows and interest are part of ordinary operations.
    if is_financial_sector:
        operating_cash_flow_display = None
        free_cash_flow_display = None
        free_cash_flow_margin = None
        operating_margin = None
        cash_conversion = None
        interest_coverage = None
        debt_to_ebitda = None
        net_debt = None
        net_debt_to_ebitda = None
        free_cash_flow_yield = None
        cash_ratio = None
    else:
        operating_cash_flow_display = operating_cash_flow
        free_cash_flow_display = free_cash_flow

    annual_income = data.get("income_stmt", pd.DataFrame())
    annual_revenue = get_row_value(annual_income, ["Total Revenue", "Operating Revenue", "Revenue"], 0)
    prior_annual_revenue = get_row_value(annual_income, ["Total Revenue", "Operating Revenue", "Revenue"], 1)
    annual_net_income = get_row_value(annual_income, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"], 0)
    prior_annual_net_income = get_row_value(annual_income, ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"], 1)
    revenue_growth = (
        annual_revenue / prior_annual_revenue - 1.0
        if annual_revenue is not None and prior_annual_revenue is not None and prior_annual_revenue > 0
        else None
    )
    net_income_growth = (
        annual_net_income / prior_annual_net_income - 1.0
        if annual_net_income is not None and prior_annual_net_income is not None and prior_annual_net_income > 0
        else None
    )

    revenue_cagr = None
    if annual_income is not None and not annual_income.empty and annual_income.shape[1] >= 3:
        oldest_index = min(3, annual_income.shape[1] - 1)
        oldest_revenue = get_row_value(annual_income, ["Total Revenue", "Operating Revenue", "Revenue"], oldest_index)
        try:
            newest_period = pd.Timestamp(annual_income.columns[0])
            oldest_period = pd.Timestamp(annual_income.columns[oldest_index])
            year_span = (newest_period - oldest_period).days / 365.25
        except Exception:
            year_span = float(oldest_index)
        if (
            annual_revenue is not None and annual_revenue > 0 and
            oldest_revenue is not None and oldest_revenue > 0 and year_span > 0
        ):
            revenue_cagr = (annual_revenue / oldest_revenue) ** (1.0 / year_span) - 1.0

    diluted_shares = get_row_value(annual_income, ["Diluted Average Shares", "Diluted Weighted Average Shares"], 0)
    prior_diluted_shares = get_row_value(annual_income, ["Diluted Average Shares", "Diluted Weighted Average Shares"], 1)
    diluted_share_change = (
        diluted_shares / prior_diluted_shares - 1.0
        if diluted_shares is not None and prior_diluted_shares is not None and prior_diluted_shares > 0
        else None
    )

    # Advanced diagnostics. Every figure below is calculated only
    # when each required source line is present. Missing accounting values are
    # never treated as zero and no peer/sector values are inferred.
    pretax_income = get_row_value(
        income_stmt,
        ["Pretax Income", "Income Before Tax"],
        col,
    )
    tax_provision = get_row_value(
        income_stmt,
        ["Tax Provision", "Income Tax Expense", "Income Tax Expense Continuing Operations"],
        col,
    )
    effective_tax_rate = None
    if pretax_income is not None and pretax_income > 0 and tax_provision is not None:
        candidate_tax_rate = tax_provision / pretax_income
        if 0.0 <= candidate_tax_rate <= 0.60:
            effective_tax_rate = candidate_tax_rate

    nopat = (
        operating_income * (1.0 - effective_tax_rate)
        if operating_income is not None and effective_tax_rate is not None
        else None
    )
    cash_and_short_term_prev = None
    total_debt_prev = None
    if previous_balance_col is not None:
        combined_cash_prev = get_row_value(
            balance_sheet, ["Cash Cash Equivalents And Short Term Investments"], previous_balance_col
        )
        cash_prev = get_row_value(
            balance_sheet, ["Cash And Cash Equivalents", "Cash Financial"], previous_balance_col
        )
        current_marketable_prev = get_row_value(
            balance_sheet, ["Other Short Term Investments"], previous_balance_col
        )
        if combined_cash_prev is not None:
            cash_and_short_term_prev = combined_cash_prev
        elif cash_prev is not None:
            cash_and_short_term_prev = cash_prev + (current_marketable_prev or 0.0)

        total_debt_prev = get_row_value(balance_sheet, ["Total Debt"], previous_balance_col)
        if total_debt_prev is None:
            current_debt_prev = get_row_value(
                balance_sheet,
                ["Current Debt", "Current Debt And Capital Lease Obligation"],
                previous_balance_col,
            )
            long_term_debt_prev = get_row_value(
                balance_sheet,
                ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
                previous_balance_col,
            )
            if current_debt_prev is not None and long_term_debt_prev is not None:
                total_debt_prev = current_debt_prev + long_term_debt_prev

    invested_capital = (
        total_debt + stockholder_equity - cash_and_short_term
        if total_debt is not None and stockholder_equity is not None and cash_and_short_term is not None
        else None
    )
    invested_capital_prev = (
        total_debt_prev + stockholder_equity_prev - cash_and_short_term_prev
        if total_debt_prev is not None and stockholder_equity_prev is not None and cash_and_short_term_prev is not None
        else None
    )
    average_invested_capital = (
        (invested_capital + invested_capital_prev) / 2.0
        if invested_capital is not None and invested_capital_prev is not None
        else None
    )
    roic = (
        nopat / average_invested_capital
        if not is_financial_sector and nopat is not None and average_invested_capital is not None and average_invested_capital > 0
        else None
    )

    # DuPont identity uses the same TTM numerator and average balance-sheet
    # denominators as the headline ROE calculation.
    equity_multiplier = (
        avg_total_assets / avg_stockholder_equity
        if avg_total_assets is not None and avg_stockholder_equity is not None and avg_stockholder_equity > 0
        else None
    )
    dupont_roe = (
        net_margin * asset_turnover * equity_multiplier
        if net_margin is not None and asset_turnover is not None and equity_multiplier is not None
        else None
    )

    receivables_prev = get_row_value(
        balance_sheet,
        ["Receivables", "Accounts Receivable", "Current Receivables"],
        previous_balance_col,
    ) if previous_balance_col is not None else None
    inventory_prev = get_row_value(balance_sheet, ["Inventory"], previous_balance_col) if previous_balance_col is not None else None
    accounts_payable = get_row_value(
        balance_sheet, ["Payables", "Accounts Payable", "Payables And Accrued Expenses"], col
    )
    accounts_payable_prev = get_row_value(
        balance_sheet,
        ["Payables", "Accounts Payable", "Payables And Accrued Expenses"],
        previous_balance_col,
    ) if previous_balance_col is not None else None
    cost_of_revenue = get_row_value(
        income_stmt, ["Cost Of Revenue", "Cost Of Goods Sold", "Reconciled Cost Of Revenue"], col
    )
    if cost_of_revenue is None and revenue is not None and gross_profit is not None:
        cost_of_revenue = revenue - gross_profit

    def average_balance(current_value: Optional[float], prior_value: Optional[float]) -> Optional[float]:
        if current_value is None or prior_value is None:
            return None
        return (current_value + prior_value) / 2.0

    avg_receivables = average_balance(receivables, receivables_prev)
    avg_inventory = average_balance(inventory, inventory_prev)
    avg_accounts_payable = average_balance(accounts_payable, accounts_payable_prev)
    dso = (
        365.0 * avg_receivables / revenue
        if not is_financial_sector and avg_receivables is not None and revenue is not None and revenue > 0
        else None
    )
    dio = (
        365.0 * avg_inventory / cost_of_revenue
        if not is_financial_sector and avg_inventory is not None and cost_of_revenue is not None and cost_of_revenue > 0
        else None
    )
    dpo = (
        365.0 * avg_accounts_payable / cost_of_revenue
        if not is_financial_sector and avg_accounts_payable is not None and cost_of_revenue is not None and cost_of_revenue > 0
        else None
    )
    cash_conversion_cycle = dso + dio - dpo if dso is not None and dio is not None and dpo is not None else None
    accrual_ratio = (
        (net_income - operating_cash_flow) / avg_total_assets
        if not is_financial_sector and net_income is not None and operating_cash_flow is not None and avg_total_assets is not None and avg_total_assets > 0
        else None
    )
    operating_cash_flow_margin = (
        operating_cash_flow / revenue
        if not is_financial_sector and operating_cash_flow is not None and revenue is not None and revenue > 0
        else None
    )
    capex_to_revenue = (
        abs(capital_expenditure) / revenue
        if not is_financial_sector and capital_expenditure is not None and revenue is not None and revenue > 0
        else None
    )
    stock_based_compensation = get_row_value(
        cash_flow,
        ["Stock Based Compensation", "Stock-Based Compensation", "Share Based Compensation"],
        col,
    )
    stock_comp_to_revenue = (
        stock_based_compensation / revenue
        if stock_based_compensation is not None and revenue is not None and revenue > 0
        else None
    )
    stock_comp_to_fcf = (
        stock_based_compensation / free_cash_flow
        if stock_based_compensation is not None and free_cash_flow is not None and free_cash_flow > 0
        else None
    )
    research_and_development = get_row_value(
        income_stmt,
        ["Research And Development", "Research Development", "Research And Development Expense"],
        col,
    )
    research_and_development_intensity = (
        research_and_development / revenue
        if research_and_development is not None and revenue is not None and revenue > 0
        else None
    )

    price_to_sales = (
        market_cap / revenue
        if currencies_compatible and market_cap is not None and revenue is not None and revenue > 0
        else None
    )
    price_to_book = (
        market_cap / stockholder_equity
        if currencies_compatible and market_cap is not None and stockholder_equity is not None and stockholder_equity > 0
        else None
    )
    ev_to_sales = (
        enterprise_value_std / revenue
        if enterprise_value_std is not None and revenue is not None and revenue > 0
        else None
    )
    earnings_yield = (
        net_income / market_cap
        if currencies_compatible and net_income is not None and net_income > 0 and market_cap is not None and market_cap > 0
        else None
    )

    cash_dividends_paid = get_row_value(
        cash_flow,
        ["Cash Dividends Paid", "Common Stock Dividend Paid", "Payment Of Dividends"],
        col,
    )
    stock_repurchase = get_row_value(
        cash_flow,
        ["Repurchase Of Capital Stock", "Repurchase Of Stock", "Common Stock Issuance Or Purchase"],
        col,
    )
    stock_issuance = get_row_value(
        cash_flow,
        ["Issuance Of Capital Stock", "Common Stock Issuance", "Proceeds From Stock Option Exercised"],
        col,
    )
    dividends_paid_abs = abs(cash_dividends_paid) if cash_dividends_paid is not None else None
    repurchases_abs = abs(stock_repurchase) if stock_repurchase is not None else None
    issuances_abs = abs(stock_issuance) if stock_issuance is not None else None
    net_buybacks = (
        repurchases_abs - issuances_abs
        if repurchases_abs is not None and issuances_abs is not None
        else None
    )
    dividend_yield_cash_flow = (
        dividends_paid_abs / market_cap
        if currencies_compatible and dividends_paid_abs is not None and market_cap is not None and market_cap > 0
        else None
    )
    net_buyback_yield = (
        net_buybacks / market_cap
        if currencies_compatible and net_buybacks is not None and market_cap is not None and market_cap > 0
        else None
    )
    shareholder_yield = (
        (dividends_paid_abs + net_buybacks) / market_cap
        if currencies_compatible and dividends_paid_abs is not None and net_buybacks is not None and market_cap is not None and market_cap > 0
        else None
    )

    analysis_diluted_shares = get_row_value(
        income_stmt, ["Diluted Average Shares", "Diluted Weighted Average Shares"], col
    )
    balance_sheet_shares = get_row_value(
        balance_sheet,
        ["Ordinary Shares Number", "Share Issued", "Common Stock Shares Outstanding"],
        col,
    )
    revenue_per_share = (
        revenue / analysis_diluted_shares
        if revenue is not None and analysis_diluted_shares is not None and analysis_diluted_shares > 0
        else None
    )
    free_cash_flow_per_share = (
        free_cash_flow / analysis_diluted_shares
        if free_cash_flow is not None and analysis_diluted_shares is not None and analysis_diluted_shares > 0
        else None
    )
    book_value_per_share = (
        stockholder_equity / balance_sheet_shares
        if stockholder_equity is not None and balance_sheet_shares is not None and balance_sheet_shares > 0
        else None
    )

    annual_cash_flow = data.get("cash_flow", pd.DataFrame())
    annual_fcf = get_row_value(annual_cash_flow, ["Free Cash Flow"], 0)
    prior_annual_fcf = get_row_value(annual_cash_flow, ["Free Cash Flow"], 1)
    if annual_fcf is None:
        annual_ocf = get_row_value(annual_cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"], 0)
        annual_capex = get_row_value(annual_cash_flow, ["Capital Expenditure", "Capital Expenditures"], 0)
        if annual_ocf is not None and annual_capex is not None:
            annual_fcf = annual_ocf + annual_capex if annual_capex < 0 else annual_ocf - annual_capex
    if prior_annual_fcf is None:
        prior_annual_ocf = get_row_value(annual_cash_flow, ["Operating Cash Flow", "Total Cash From Operating Activities"], 1)
        prior_annual_capex = get_row_value(annual_cash_flow, ["Capital Expenditure", "Capital Expenditures"], 1)
        if prior_annual_ocf is not None and prior_annual_capex is not None:
            prior_annual_fcf = prior_annual_ocf + prior_annual_capex if prior_annual_capex < 0 else prior_annual_ocf - prior_annual_capex
    annual_fcf_growth = (
        annual_fcf / prior_annual_fcf - 1.0
        if annual_fcf is not None and prior_annual_fcf is not None and prior_annual_fcf > 0
        else None
    )
    annual_diluted_eps = get_row_value(annual_income, ["Diluted EPS", "Diluted EPS Continuing Operations"], 0)
    prior_annual_diluted_eps = get_row_value(annual_income, ["Diluted EPS", "Diluted EPS Continuing Operations"], 1)
    annual_eps_growth = (
        annual_diluted_eps / prior_annual_diluted_eps - 1.0
        if annual_diluted_eps is not None and prior_annual_diluted_eps is not None and prior_annual_diluted_eps > 0
        else None
    )
    prior_revenue_per_share = (
        prior_annual_revenue / prior_diluted_shares
        if prior_annual_revenue is not None and prior_diluted_shares is not None and prior_diluted_shares > 0
        else None
    )
    annual_revenue_per_share = (
        annual_revenue / diluted_shares
        if annual_revenue is not None and diluted_shares is not None and diluted_shares > 0
        else None
    )
    revenue_per_share_growth = (
        annual_revenue_per_share / prior_revenue_per_share - 1.0
        if annual_revenue_per_share is not None and prior_revenue_per_share is not None and prior_revenue_per_share > 0
        else None
    )

    advanced_metrics = {
        "roic": roic,
        "effective_tax_rate": effective_tax_rate,
        "nopat": nopat,
        "invested_capital": invested_capital,
        "dupont_net_margin": net_margin,
        "dupont_asset_turnover": asset_turnover,
        "dupont_equity_multiplier": equity_multiplier,
        "dupont_roe": dupont_roe,
        "dso": dso,
        "dio": dio,
        "dpo": dpo,
        "cash_conversion_cycle": cash_conversion_cycle,
        "accrual_ratio": accrual_ratio,
        "operating_cash_flow_margin": operating_cash_flow_margin,
        "capex_to_revenue": capex_to_revenue,
        "stock_comp_to_revenue": stock_comp_to_revenue,
        "stock_comp_to_fcf": stock_comp_to_fcf,
        "research_and_development_intensity": research_and_development_intensity,
        "price_to_sales": price_to_sales,
        "price_to_book": price_to_book,
        "ev_to_sales": ev_to_sales,
        "earnings_yield": earnings_yield,
        "dividend_yield_cash_flow": dividend_yield_cash_flow,
        "net_buyback_yield": net_buyback_yield,
        "shareholder_yield": shareholder_yield,
        "revenue_per_share": revenue_per_share,
        "free_cash_flow_per_share": free_cash_flow_per_share,
        "book_value_per_share": book_value_per_share,
        "annual_eps_growth": annual_eps_growth,
        "annual_fcf_growth": annual_fcf_growth,
        "revenue_per_share_growth": revenue_per_share_growth,
    }

    supplemental_metrics = {
        "working_capital": working_capital,
        "cash_ratio": cash_ratio,
        "operating_cash_flow": operating_cash_flow_display,
        "capital_expenditure": capital_expenditure,
        "free_cash_flow": free_cash_flow_display,
        "free_cash_flow_method": free_cash_flow_method,
        "free_cash_flow_margin": free_cash_flow_margin,
        "free_cash_flow_yield": free_cash_flow_yield,
        "cash_conversion": cash_conversion,
        "interest_coverage": interest_coverage,
        "debt_to_ebitda": debt_to_ebitda,
        "net_debt": net_debt,
        "net_debt_to_ebitda": net_debt_to_ebitda,
        "operating_margin": operating_margin,
        "annual_revenue_growth": revenue_growth,
        "annual_net_income_growth": net_income_growth,
        "revenue_cagr": revenue_cagr,
        "diluted_share_change": diluted_share_change,
    }

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
    health_evaluation = evaluate_connected_financial_model(
        ratios,
        supplemental_metrics,
        advanced_metrics,
        is_financial_sector=is_financial_sector,
        eps_ttm=eps_ttm,
        equity=stockholder_equity,
        sector=info.get("sector"),
        industry=info.get("industry"),
    )
    integrity_hold_reason = data.get("integrity_hold_reason")
    if integrity_hold_reason:
        health_evaluation["score"] = None
        health_evaluation["status"] = "Verification Hold"
        health_evaluation["coverage"]["sufficient_for_score"] = False
        health_evaluation["coverage"]["withheld_reason"] = integrity_hold_reason

    core_inputs = {
        "revenue": revenue,
        "gross_profit": gross_profit,
        "operating_income": operating_income,
        "net_income": net_income,
        "total_assets": total_assets,
        "stockholders_equity": stockholder_equity,
        "current_assets": current_assets,
        "current_liabilities": current_liabilities,
        "cash_and_short_term_investments": cash_and_short_term,
        "total_debt": total_debt,
        "operating_cash_flow": operating_cash_flow,
        "capital_expenditure": capital_expenditure,
        "trailing_eps": eps_ttm,
        "market_cap": market_cap,
    }
    available_core_inputs = [name for name, value in core_inputs.items() if value is not None]
    missing_core_inputs = [name for name, value in core_inputs.items() if value is None]

    formula_map = {
        "current_ratio": "Current assets / current liabilities",
        "quick_ratio": "(Cash + short-term investments + receivables) / current liabilities",
        "debt_to_equity": "Total debt / stockholders' equity",
        "gross_margin": "Gross profit / revenue",
        "net_margin": "Net income / revenue",
        "roe": "Net income / average stockholders' equity",
        "roa": "Net income / average total assets",
        "asset_turnover": "Revenue / average total assets",
        "pe_ratio": "Current share price / trailing-twelve-month diluted EPS",
        "ev_ebitda": "(Market cap + debt - cash and short-term investments) / EBITDA",
    }
    for key, item in health_evaluation["evaluations"].items():
        item.setdefault("formula", formula_map.get(key))
        item["period_basis"] = analysis_basis

    return {
        "symbol": symbol,
        "is_financial_sector": is_financial_sector,
        "ratios": ratios,
        "health_score": health_evaluation["score"],
        "health_status": health_evaluation["status"],
        "valuation_score": health_evaluation.get("valuation_score"),
        "valuation_status": health_evaluation.get("valuation_status"),
        "financial_health_components": health_evaluation.get("component_scores") or {},
        "applicability_profile": health_evaluation.get("applicability_profile") or {},
        "model_disclosure": health_evaluation.get("model_disclosure"),
        "score_coverage": health_evaluation["coverage"],
        "calculation_coverage": {
            "available_core_input_count": len(available_core_inputs),
            "core_input_count": len(core_inputs),
            "available_core_inputs": available_core_inputs,
            "missing_core_inputs": missing_core_inputs,
        },
        "ratio_evaluations": health_evaluation["evaluations"],
        "analysis_basis": analysis_basis,
        "ev_breakdown": {
            "market_cap": market_cap,
            "market_cap_method": market_cap_method,
            "share_count_used": share_count,
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
            "statement_data_provider": info.get("statement_data_provider"),
            "market_currency": market_currency,
            "statement_currency": statement_currency,
            "currencies_compatible": currencies_compatible,
        },
        "supplemental_metrics": supplemental_metrics,
        "advanced_metrics": advanced_metrics,
        "advanced_metric_scope": {
            "score_effect": (
                "Metrics explicitly labelled Health score input feed the financial-health model; metrics labelled "
                "Valuation score input feed the separate valuation screen; Context only metrics do not affect either score."
            ),
            "missing_value_policy": "N/A means one or more exact source inputs were not reported; no value was estimated.",
            "period_basis": analysis_basis,
            "financial_institution_model": (
                "Generic industrial cash-flow, working-capital, ROIC, and enterprise-value metrics are withheld. "
                "Regulatory sector KPIs require issuer-reported source lines and are not inferred."
                if is_financial_sector else None
            ),
        },
        "raw_financials": {
            "revenue": revenue,
            "gross_profit": gross_profit,
            "net_income": net_income,
            "operating_income": operating_income,
            "depreciation_amortization": depreciation_amortization,
            "ebitda": ebitda,
            "total_assets": total_assets,
            "average_total_assets": avg_total_assets,
            "total_debt": total_debt,
            "stockholder_equity": stockholder_equity,
            "average_stockholder_equity": avg_stockholder_equity,
            "cash_and_equiv": cash_and_equiv,
            "cash_and_short_term": cash_and_short_term,
            "receivables": receivables,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "inventory": inventory,
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditure": capital_expenditure,
            "free_cash_flow": free_cash_flow,
            "interest_expense": interest_expense,
            "pretax_income": pretax_income,
            "tax_provision": tax_provision,
            "cost_of_revenue": cost_of_revenue,
            "accounts_payable": accounts_payable,
            "stock_based_compensation": stock_based_compensation,
            "cash_dividends_paid": cash_dividends_paid,
            "stock_repurchase": stock_repurchase,
            "stock_issuance": stock_issuance,
            "research_and_development": research_and_development,
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

    applicable_count = sum(
        1 for item in evaluations.values()
        if item["status"] in ["Healthy", "Caution", "Warning"]
    )
    minimum_required = 4 if is_financial_sector else 6

    # A normalized score based on one or two surviving ratios creates false
    # precision. Publish a score only after a minimum coverage threshold.
    if total_applicable_weight > 0 and applicable_count >= minimum_required:
        max_possible_points = total_applicable_weight * 100.0
        final_score = int(round((total_weighted_points / max_possible_points) * 100.0))
    else:
        final_score = None

    if final_score is None:
        overall_status = "Insufficient Data"
    elif final_score >= 80:
        overall_status = "Strong Rules-Based Screen"
    elif final_score >= 60:
        overall_status = "Moderate Rules-Based Screen"
    else:
        overall_status = "Weak Rules-Based Screen"

    return {
        "score": final_score,
        "status": overall_status,
        "evaluations": evaluations,
        "coverage": {
            "applicable_ratio_count": applicable_count,
            "model_ratio_count": len(evaluations),
            "minimum_required": minimum_required,
            "sufficient_for_score": final_score is not None,
        },
    }


def evaluate_connected_financial_model(
    ratios: Dict[str, Optional[float]],
    supplemental: Dict[str, Any],
    advanced: Dict[str, Any],
    is_financial_sector: bool = False,
    eps_ttm: Optional[float] = None,
    equity: Optional[float] = None,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
) -> Dict[str, Any]:
    """Build separate financial-health and valuation screens from connected evidence.

    The health score uses five capped components so overlapping ratios cannot
    dominate the result. Metrics without a consistently favorable direction
    remain context-only. Banks, insurers and REITs are withheld when the
    regulatory/property inputs required for a responsible sector model are not
    present in the standardized statement feed.
    """
    sector_text = str(sector or "").lower()
    industry_text = str(industry or "").lower()
    is_reit = "reit" in industry_text
    is_regulated_utility = "utilities" in sector_text or "regulated utility" in industry_text
    classification_available = bool(sector_text or industry_text)
    if not classification_available:
        profile_key = "classification_unavailable"
        profile_label = "Company type unverified"
        profile_rationale = "Sector and industry metadata are unavailable, so metric applicability cannot be verified."
    elif is_financial_sector:
        profile_key = "financial_institution"
        profile_label = "Financial institution"
        profile_rationale = "Uses a regulatory-capital and asset-quality model, not an industrial-company ratio model."
    elif is_reit:
        profile_key = "reit"
        profile_label = "REIT"
        profile_rationale = "Requires property-specific FFO/AFFO, occupancy, lease and debt-maturity evidence."
    elif is_regulated_utility:
        profile_key = "regulated_utility"
        profile_label = "Regulated utility"
        profile_rationale = "Uses operating-company evidence with utility-adjusted leverage and coverage ranges."
    else:
        profile_key = "operating_company"
        profile_label = "Operating company"
        profile_rationale = "Uses the general operating-company model; industry-sensitive measures remain context only."
    evaluations: Dict[str, Dict[str, Any]] = {}
    component_totals: Dict[str, Dict[str, float]] = {}
    model_totals = {
        "financial_health": {"expected": 0.0, "available": 0.0, "points": 0.0, "count": 0.0},
        "valuation": {"expected": 0.0, "available": 0.0, "points": 0.0, "count": 0.0},
    }

    value_map = {**ratios, **supplemental, **advanced}

    def usable(value: Any) -> bool:
        if value is None:
            return False
        try:
            return bool(np.isfinite(float(value)))
        except (TypeError, ValueError):
            return False

    def register(
        spec: Dict[str, Any],
        value: Any,
        forced_status: Optional[str] = None,
        applicability_reason: Optional[str] = None,
    ) -> None:
        model = spec.get("score_model", "context")
        weight = float(spec.get("weight", 0.0))
        component = spec.get("component")
        if model in model_totals:
            model_totals[model]["expected"] += weight
            if model == "financial_health" and component:
                component_totals.setdefault(component, {"expected": 0.0, "available": 0.0, "points": 0.0, "count": 0.0})
                component_totals[component]["expected"] += weight

        status = forced_status
        points = 0.0
        numeric_value = float(value) if usable(value) else None
        if status is None and numeric_value is None:
            status = "N/A"
        elif status is None and spec.get("positive_only") and numeric_value <= 0:
            status = "N/M"
        elif status is None:
            direction = spec["direction"]
            healthy = float(spec["healthy"])
            caution = float(spec["caution"])
            if direction == "higher":
                if numeric_value >= healthy:
                    status, points = "Healthy", 1.0
                elif numeric_value >= caution:
                    status, points = "Caution", 0.6
                else:
                    status, points = "Warning", 0.2
            else:
                if numeric_value <= healthy:
                    status, points = "Healthy", 1.0
                elif numeric_value <= caution:
                    status, points = "Caution", 0.6
                else:
                    status, points = "Warning", 0.2

        applicable = status in {"Healthy", "Caution", "Warning"}
        weighted_points = points * weight * 100.0 if applicable and model in model_totals else 0.0
        if applicable and model in model_totals:
            model_totals[model]["available"] += weight
            model_totals[model]["points"] += weighted_points
            model_totals[model]["count"] += 1
            if model == "financial_health" and component:
                component_totals[component]["available"] += weight
                component_totals[component]["points"] += weighted_points
                component_totals[component]["count"] += 1

        status_label = status
        if model == "valuation":
            status_label = {"Healthy": "Favorable", "Caution": "Mixed", "Warning": "Stretched"}.get(status, status)
        evaluations[spec["key"]] = {
            "name": spec["name"],
            "category": spec["category"],
            "component": component,
            "value": numeric_value,
            "status": status,
            "status_label": status_label,
            "target": spec["target"],
            "format": spec["format"],
            "formula": spec["formula"],
            "pts": points,
            "weight": weight if model in model_totals else 0.0,
            "w_pts": weighted_points,
            "score_model": model,
            "applicable_to_score": applicable and model in model_totals,
            "applicability_reason": applicability_reason or spec.get("applicability_reason"),
        }

    health_specs = [
        # Liquidity: 15%
        dict(key="current_ratio", name="Current Ratio", category="Liquidity", component="liquidity", weight=.05, direction="higher", healthy=1.50, caution=1.00, format="{:.2f}", target="Healthy ≥ 1.50 | Caution 1.00–1.49 | Warning < 1.00", formula="Current assets / current liabilities"),
        dict(key="quick_ratio", name="Strict Quick Ratio", category="Liquidity", component="liquidity", weight=.05, direction="higher", healthy=1.00, caution=.80, format="{:.2f}", target="Healthy ≥ 1.00 | Caution 0.80–0.99 | Warning < 0.80", formula="(Cash + short-term investments + receivables) / current liabilities"),
        dict(key="cash_ratio", name="Cash Ratio", category="Liquidity", component="liquidity", weight=.05, direction="higher", healthy=.50, caution=.20, format="{:.2f}", target="Healthy ≥ 0.50 | Caution 0.20–0.49 | Warning < 0.20", formula="Cash and short-term investments / current liabilities"),
        # Solvency: 25%
        dict(key="debt_to_equity", name="Debt-to-Equity", category="Leverage", component="solvency", weight=.05, direction="lower", healthy=1.50, caution=2.00, format="{:.2f}", target="Healthy ≤ 1.50 | Caution 1.51–2.00 | Warning > 2.00", formula="Total debt / stockholders' equity"),
        dict(key="interest_coverage", name="Interest Coverage", category="Leverage", component="solvency", weight=.07, direction="higher", healthy=5.00, caution=2.00, format="{:.2f}", target="Healthy ≥ 5.00 | Caution 2.00–4.99 | Warning < 2.00", formula="Operating income / absolute interest expense"),
        dict(key="debt_to_ebitda", name="Debt / EBITDA", category="Leverage", component="solvency", weight=.07, direction="lower", healthy=2.00, caution=4.00, format="{:.2f}", target="Healthy ≤ 2.00 | Caution 2.01–4.00 | Warning > 4.00", formula="Total debt / EBITDA"),
        dict(key="net_debt_to_ebitda", name="Net Debt / EBITDA", category="Leverage", component="solvency", weight=.06, direction="lower", healthy=1.50, caution=3.00, format="{:.2f}", target="Healthy ≤ 1.50 | Caution 1.51–3.00 | Warning > 3.00", formula="(Total debt - cash and short-term investments) / EBITDA"),
        # Profitability and efficiency: 25%
        dict(key="operating_margin", name="Operating Margin", category="Profitability", component="profitability_efficiency", weight=.05, direction="higher", healthy=.15, caution=.05, format="{:.1%}", target="Healthy ≥ 15% | Caution 5%–14.9% | Warning < 5%", formula="Operating income / revenue"),
        dict(key="net_margin", name="Net Margin", category="Profitability", component="profitability_efficiency", weight=.04, direction="higher", healthy=.15, caution=.05, format="{:.1%}", target="Healthy ≥ 15% | Caution 5%–14.9% | Warning < 5%", formula="Net income / revenue"),
        dict(key="roa", name="Return on Assets (ROA)", category="Profitability", component="profitability_efficiency", weight=.04, direction="higher", healthy=.08, caution=.03, format="{:.1%}", target="Healthy ≥ 8% | Caution 3%–7.9% | Warning < 3%", formula="Net income / average total assets"),
        dict(key="roe", name="Return on Equity (ROE)", category="Profitability", component="profitability_efficiency", weight=.02, direction="higher", healthy=.15, caution=.08, format="{:.1%}", target="Healthy ≥ 15% | Caution 8%–14.9% | Warning < 8%", formula="Net income / average stockholders' equity"),
        dict(key="roic", name="Return on Invested Capital", category="Profitability", component="profitability_efficiency", weight=.06, direction="higher", healthy=.12, caution=.06, format="{:.1%}", target="Healthy ≥ 12% | Caution 6%–11.9% | Warning < 6%", formula="NOPAT / average invested capital"),
        dict(key="operating_cash_flow_margin", name="Operating Cash Flow Margin", category="Profitability", component="profitability_efficiency", weight=.04, direction="higher", healthy=.12, caution=.05, format="{:.1%}", target="Healthy ≥ 12% | Caution 5%–11.9% | Warning < 5%", formula="Operating cash flow / revenue"),
        # Cash-flow quality: 20%
        dict(key="free_cash_flow_margin", name="Free Cash Flow Margin", category="Profitability", component="cash_flow_quality", weight=.08, direction="higher", healthy=.10, caution=0.00, format="{:.1%}", target="Healthy ≥ 10% | Caution 0%–9.9% | Warning < 0%", formula="Free cash flow / revenue"),
        dict(key="cash_conversion", name="Cash Conversion", category="Efficiency", component="cash_flow_quality", weight=.06, direction="higher", healthy=1.00, caution=.80, format="{:.2f}", target="Healthy ≥ 1.00 | Caution 0.80–0.99 | Warning < 0.80", formula="Operating cash flow / net income"),
        dict(key="accrual_ratio", name="Accrual Ratio", category="Profitability", component="cash_flow_quality", weight=.06, direction="lower", healthy=0.00, caution=.10, format="{:.1%}", target="Healthy ≤ 0% | Caution 0.1%–10% | Warning > 10%", formula="(Net income - operating cash flow) / average assets"),
        # Growth and per-share resilience: 15%
        dict(key="annual_revenue_growth", name="Annual Revenue Growth", category="Growth", component="growth_per_share", weight=.035, direction="higher", healthy=.05, caution=0.00, format="{:.1%}", target="Healthy ≥ 5% | Caution 0%–4.9% | Warning < 0%", formula="Latest annual revenue / prior annual revenue - 1"),
        dict(key="annual_net_income_growth", name="Annual Net Income Growth", category="Growth", component="growth_per_share", weight=.02, direction="higher", healthy=.05, caution=0.00, format="{:.1%}", target="Healthy ≥ 5% | Caution 0%–4.9% | Warning < 0%", formula="Latest annual net income / prior annual net income - 1"),
        dict(key="annual_eps_growth", name="Annual Diluted EPS Growth", category="Growth", component="growth_per_share", weight=.03, direction="higher", healthy=.05, caution=0.00, format="{:.1%}", target="Healthy ≥ 5% | Caution 0%–4.9% | Warning < 0%", formula="Latest annual diluted EPS / prior annual diluted EPS - 1"),
        dict(key="annual_fcf_growth", name="Annual Free Cash Flow Growth", category="Growth", component="growth_per_share", weight=.025, direction="higher", healthy=.05, caution=0.00, format="{:.1%}", target="Healthy ≥ 5% | Caution 0%–4.9% | Warning < 0%", formula="Latest annual free cash flow / prior annual free cash flow - 1"),
        dict(key="revenue_per_share_growth", name="Revenue-per-Share Growth", category="Growth", component="growth_per_share", weight=.025, direction="higher", healthy=.05, caution=0.00, format="{:.1%}", target="Healthy ≥ 5% | Caution 0%–4.9% | Warning < 0%", formula="Latest annual revenue per diluted share / prior year - 1"),
        dict(key="diluted_share_change", name="Diluted Share Change", category="Capital allocation", component="growth_per_share", weight=.015, direction="lower", healthy=0.00, caution=.02, format="{:.1%}", target="Healthy ≤ 0% | Caution 0.1%–2% | Warning > 2%", formula="Latest annual diluted average shares / prior year - 1"),
    ]
    context_specs = [
        dict(key="gross_margin", name="Gross Margin", category="Profitability", component=None, weight=0.0, direction="higher", healthy=.40, caution=.20, format="{:.1%}", target="Context only: desirable levels vary materially by industry", formula="Gross profit / revenue", score_model="context"),
        dict(key="asset_turnover", name="Asset Turnover", category="Efficiency", component=None, weight=0.0, direction="higher", healthy=.75, caution=.40, format="{:.2f}", target="Context only: asset intensity varies materially by industry", formula="Revenue / average total assets", score_model="context"),
        dict(key="effective_tax_rate", name="Effective Tax Rate", category="Profitability", component=None, weight=0.0, direction="higher", healthy=.15, caution=0.00, format="{:.1%}", target="Context only: tax rates reflect jurisdiction and one-time items", formula="Tax provision / pretax income", score_model="context"),
    ]
    valuation_specs = [
        dict(key="pe_ratio", name="TTM P/E Ratio", category="Valuation", component=None, weight=.25, direction="lower", healthy=25.0, caution=40.0, format="{:.2f}", target="Favorable ≤ 25.0 | Mixed 25.1–40.0 | Stretched > 40.0", formula="Current share price / trailing diluted EPS", score_model="valuation", positive_only=True),
        dict(key="ev_ebitda", name="EV / EBITDA", category="Valuation", component=None, weight=.25, direction="lower", healthy=15.0, caution=25.0, format="{:.2f}", target="Favorable ≤ 15.0 | Mixed 15.1–25.0 | Stretched > 25.0", formula="Enterprise value / EBITDA", score_model="valuation", positive_only=True),
        dict(key="free_cash_flow_yield", name="Free Cash Flow Yield", category="Valuation", component=None, weight=.20, direction="higher", healthy=.05, caution=.02, format="{:.1%}", target="Favorable ≥ 5% | Mixed 2%–4.9% | Stretched < 2%", formula="Free cash flow / market capitalization", score_model="valuation"),
        dict(key="price_to_sales", name="Price / Sales", category="Valuation", component=None, weight=.10, direction="lower", healthy=4.0, caution=8.0, format="{:.2f}", target="Favorable ≤ 4.0 | Mixed 4.1–8.0 | Stretched > 8.0", formula="Market capitalization / TTM revenue", score_model="valuation", positive_only=True),
        dict(key="price_to_book", name="Price / Book", category="Valuation", component=None, weight=.10, direction="lower", healthy=3.0, caution=6.0, format="{:.2f}", target="Favorable ≤ 3.0 | Mixed 3.1–6.0 | Stretched > 6.0", formula="Market capitalization / stockholders' equity", score_model="valuation", positive_only=True),
        dict(key="ev_to_sales", name="Enterprise Value / Sales", category="Valuation", component=None, weight=.10, direction="lower", healthy=4.0, caution=8.0, format="{:.2f}", target="Favorable ≤ 4.0 | Mixed 4.1–8.0 | Stretched > 8.0", formula="Enterprise value / TTM revenue", score_model="valuation", positive_only=True),
    ]

    applicability_hold = None
    if not classification_available:
        applicability_hold = (
            "Financial-health score withheld because current sector and industry metadata are unavailable; "
            "the site cannot verify which financial model applies."
        )
    elif is_financial_sector:
        applicability_hold = (
            "Financial-health score withheld because banks, insurers and similar institutions require regulatory capital, "
            "asset-quality and funding-liquidity inputs that are not consistently available in the standardized statement feed."
        )
    elif is_reit:
        applicability_hold = (
            "Financial-health score withheld because REIT analysis requires FFO/AFFO, occupancy, lease maturity and property-level debt inputs."
        )

    utility_overrides = {
        "current_ratio": (1.00, .70, "Healthy ≥ 1.00 | Caution 0.70–0.99 | Warning < 0.70 (utility-adjusted)"),
        "debt_to_equity": (2.00, 3.00, "Healthy ≤ 2.00 | Caution 2.01–3.00 | Warning > 3.00 (utility-adjusted)"),
        "interest_coverage": (3.00, 1.50, "Healthy ≥ 3.00 | Caution 1.50–2.99 | Warning < 1.50 (utility-adjusted)"),
        "debt_to_ebitda": (4.00, 5.50, "Healthy ≤ 4.00 | Caution 4.01–5.50 | Warning > 5.50 (utility-adjusted)"),
        "net_debt_to_ebitda": (3.50, 5.00, "Healthy ≤ 3.50 | Caution 3.51–5.00 | Warning > 5.00 (utility-adjusted)"),
    }

    for base_spec in health_specs:
        spec = {**base_spec, "score_model": "context" if applicability_hold else "financial_health", "weight": 0.0 if applicability_hold else base_spec["weight"]}
        if is_regulated_utility and spec["key"] in utility_overrides:
            healthy, caution, target = utility_overrides[spec["key"]]
            spec.update(healthy=healthy, caution=caution, target=target)
        value = value_map.get(spec["key"])
        forced = None
        if equity is not None and equity <= 0 and spec["key"] in {"debt_to_equity", "roe"}:
            forced = "N/M"
        if is_financial_sector and spec["key"] in {"current_ratio", "quick_ratio", "cash_ratio"}:
            value = None
        applicability_reason = None
        if applicability_hold:
            forced = "Context" if usable(value) else "N/A"
            applicability_reason = applicability_hold
        register(spec, value, forced_status=forced, applicability_reason=applicability_reason)

    for spec in context_specs:
        value = None if is_financial_sector and spec["key"] == "gross_margin" else value_map.get(spec["key"])
        register(
            spec,
            value,
            forced_status="Context" if usable(value) else "N/A",
            applicability_reason=spec["target"],
        )

    active_valuation_specs = valuation_specs
    if not classification_available:
        active_valuation_specs = []
    elif is_financial_sector:
        # Enterprise value and industrial cash-flow multiples are not meaningful
        # for deposit-funded institutions; use only P/E and P/B when both exist.
        active_valuation_specs = [
            {**valuation_specs[0], "weight": .50},
            {**valuation_specs[4], "weight": .50},
        ]
    elif is_reit:
        active_valuation_specs = []
    for spec in active_valuation_specs:
        forced = "N/M" if spec["key"] == "pe_ratio" and eps_ttm is not None and eps_ttm <= 0 else None
        register(spec, value_map.get(spec["key"]), forced_status=forced)
    active_valuation_keys = {spec["key"] for spec in active_valuation_specs}
    for base_spec in valuation_specs:
        if base_spec["key"] in active_valuation_keys:
            continue
        if not classification_available:
            reason = "Not scored until current sector and industry metadata establish the applicable company model."
        elif is_financial_sector:
            reason = "Not used for deposit-funded financial institutions; the separate valuation screen uses P/E and P/B."
        else:
            reason = "Not scored for REITs without FFO/AFFO and property-specific valuation inputs."
        register(
            {**base_spec, "score_model": "context", "weight": 0.0},
            value_map.get(base_spec["key"]),
            forced_status="Context" if usable(value_map.get(base_spec["key"])) else "N/A",
            applicability_reason=reason,
        )

    health_total = model_totals["financial_health"]
    health_coverage = health_total["available"] / health_total["expected"] if health_total["expected"] else 0.0
    covered_components = sum(1 for values in component_totals.values() if values["available"] > 0)
    health_score = None
    if not applicability_hold and health_coverage >= .80 and covered_components == 5:
        health_score = int(round(health_total["points"] / (health_total["available"] * 100.0) * 100.0))

    health_score_range = None
    if health_score is not None and health_total["expected"] > 0:
        missing_weight = max(health_total["expected"] - health_total["available"], 0.0)
        health_score_range = {
            "low": int(round(health_total["points"] / (health_total["expected"] * 100.0) * 100.0)),
            "high": int(round((health_total["points"] + missing_weight * 100.0) / (health_total["expected"] * 100.0) * 100.0)),
        }

    if health_score is None:
        health_status = (
            "Company Classification Required" if not classification_available else
            "Sector Model Required" if applicability_hold else
            "Insufficient Data"
        )
    elif health_score >= 80:
        health_status = "Strong Financial Condition Screen"
    elif health_score >= 60:
        health_status = "Moderate Financial Condition Screen"
    else:
        health_status = "Weak Financial Condition Screen"

    component_scores = {}
    component_labels = {
        "liquidity": "Liquidity",
        "solvency": "Solvency",
        "profitability_efficiency": "Profitability & efficiency",
        "cash_flow_quality": "Cash-flow quality",
        "growth_per_share": "Growth & per-share resilience",
    }
    for key, values in component_totals.items():
        score = (
            int(round(values["points"] / (values["available"] * 100.0) * 100.0))
            if values["available"] > 0 else None
        )
        component_scores[key] = {
            "label": component_labels[key],
            "score": score,
            "coverage": values["available"] / values["expected"] if values["expected"] else 0.0,
            "available_metric_count": int(values["count"]),
        }

    valuation_total = model_totals["valuation"]
    valuation_coverage = valuation_total["available"] / valuation_total["expected"] if valuation_total["expected"] else 0.0
    minimum_valuation_metrics = 2 if is_financial_sector else 3
    valuation_score = None
    if not is_reit and valuation_coverage >= .50 and valuation_total["count"] >= minimum_valuation_metrics:
        valuation_score = int(round(valuation_total["points"] / (valuation_total["available"] * 100.0) * 100.0))
    if not classification_available:
        valuation_status = "Company Classification Required"
    elif is_reit:
        valuation_status = "REIT Valuation Inputs Required"
    elif valuation_score is None:
        valuation_status = "Insufficient Data"
    elif valuation_score >= 80:
        valuation_status = "Lower-Multiple Screen"
    elif valuation_score >= 60:
        valuation_status = "Mixed Valuation Screen"
    else:
        valuation_status = "Higher-Multiple Screen"

    coverage_label = "High" if health_coverage >= .90 else ("Moderate" if health_coverage >= .80 else "Low")
    return {
        "score": health_score,
        "status": health_status,
        "valuation_score": valuation_score,
        "valuation_status": valuation_status,
        "component_scores": component_scores,
        "applicability_profile": {
            "key": profile_key,
            "label": profile_label,
            "rationale": profile_rationale,
            "sector": sector,
            "industry": industry,
            "health_model_available": applicability_hold is None,
        },
        "evaluations": evaluations,
        "coverage": {
            "applicable_ratio_count": int(health_total["count"]),
            "model_ratio_count": len(health_specs),
            "minimum_required": "80% model weight with evidence in all five components",
            "sufficient_for_score": health_score is not None,
            "coverage_percent": health_coverage,
            "coverage_label": coverage_label,
            "covered_component_count": covered_components,
            "component_count": 5,
            "score_range": health_score_range,
            "valuation_score": valuation_score,
            "valuation_status": valuation_status,
            "valuation_coverage_percent": valuation_coverage,
            "withheld_reason": applicability_hold,
        },
        "model_disclosure": (
            "Financial health and valuation are separate rules-based screens, not investment recommendations. "
            "Health uses five capped evidence components; unavailable metrics reduce coverage and are never estimated. "
            "The company profile is selected from current sector, industry and statement evidence for every searched ticker. "
            "Context-only or non-applicable metrics remain visible but contribute no points."
        ),
    }
