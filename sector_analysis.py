"""Sector-specific coverage without inferred or hard-coded issuer KPIs."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

import pandas as pd


def _value(df: pd.DataFrame, names: Iterable[str], column: int = 0) -> Optional[float]:
    if df is None or df.empty or column >= df.shape[1]:
        return None
    index_lookup = {str(index).strip().lower(): position for position, index in enumerate(df.index)}
    for name in names:
        position = index_lookup.get(name.strip().lower())
        if position is None:
            continue
        try:
            raw = df.iloc[position, column]
            return float(raw) if pd.notna(raw) else None
        except Exception:
            continue
    return None


def _entry(key: str, name: str, value: Optional[float], value_type: str, formula: str, source: str) -> Dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "value": value,
        "value_type": value_type,
        "formula": formula,
        "source": source,
        "status": "available" if value is not None else "not_reported",
    }


def prepare_sector_analysis(data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    info = data.get("info") or {}
    industry = str(info.get("industry") or "").lower()
    sector = str(info.get("sector") or "").lower()
    income = data.get("analysis_income_stmt", data.get("income_stmt", pd.DataFrame()))
    balance = data.get("analysis_balance_sheet", data.get("balance_sheet", pd.DataFrame()))
    cash_flow = data.get("analysis_cash_flow", data.get("cash_flow", pd.DataFrame()))
    advanced = metrics.get("advanced_metrics") or {}
    raw = metrics.get("raw_financials") or {}

    model = "general_corporate"
    label = "General corporate"
    metrics_list = []
    required_not_standardized = []

    if any(term in industry for term in ("bank", "financial conglomerate")):
        model = "banking"
        label = "Banking"
        net_interest_income = _value(income, ("Net Interest Income",))
        provision = _value(income, ("Provision For Loan Losses", "Credit Losses Provision"))
        loans = _value(balance, ("Net Loans", "Loans Receivable", "Gross Loans"))
        deposits = _value(balance, ("Total Deposits", "Deposits"))
        loan_to_deposit = loans / deposits if loans is not None and deposits is not None and deposits > 0 else None
        cet1_ratio = _value(balance, ("Common Equity Tier 1 Ratio", "CET1 Ratio"))
        net_interest_margin = _value(income, ("Net Interest Margin",))
        metrics_list = [
            _entry("net_interest_income", "Net interest income", net_interest_income, "money", "Directly reported line", "Income statement"),
            _entry("credit_loss_provision", "Credit-loss provision", provision, "money", "Directly reported line", "Income statement"),
            _entry("loan_to_deposit", "Loan-to-deposit ratio", loan_to_deposit, "percent", "Reported net loans / reported total deposits", "Balance sheet"),
            _entry("cet1_ratio", "CET1 ratio", cet1_ratio, "percent", "Directly reported regulatory ratio only", "Issuer filing"),
            _entry("net_interest_margin", "Net interest margin", net_interest_margin, "percent", "Directly reported ratio only", "Issuer filing"),
        ]
        required_not_standardized = ["Efficiency ratio", "Non-performing loan ratio", "Reserve coverage", "Risk-weighted assets"]
    elif "insurance" in industry:
        model = "insurance"
        label = "Insurance"
        premiums = _value(income, ("Insurance Revenue", "Net Premiums Earned", "Premiums Earned"))
        claims = _value(income, ("Policyholder Benefits And Claims", "Losses And Loss Adjustment Expense"))
        loss_ratio = abs(claims) / premiums if claims is not None and premiums is not None and premiums > 0 else None
        metrics_list = [
            _entry("premiums", "Insurance revenue / premiums", premiums, "money", "Directly reported line", "Income statement"),
            _entry("claims", "Claims and policyholder benefits", claims, "money", "Directly reported line", "Income statement"),
            _entry("loss_ratio", "Loss ratio", loss_ratio, "percent", "Absolute reported claims / reported premiums", "Income statement"),
        ]
        required_not_standardized = ["Expense ratio", "Combined ratio", "Reserve development", "Statutory solvency capital"]
    elif "reit" in industry:
        model = "reit"
        label = "REIT"
        net_income = raw.get("net_income")
        depreciation = raw.get("depreciation_amortization")
        property_gain = _value(income, ("Gain On Sale Of Property Plant Equipment", "Gain On Sale Of Real Estate"))
        ffo = (
            net_income + depreciation - property_gain
            if net_income is not None and depreciation is not None and property_gain is not None
            else None
        )
        metrics_list = [
            _entry("ffo", "Funds from operations (FFO)", ffo, "money", "Net income + reported D&A - reported property-sale gains", "Statements"),
            _entry("net_debt_to_ebitda", "Net debt / EBITDA", (metrics.get("supplemental_metrics") or {}).get("net_debt_to_ebitda"), "multiple", "Net debt / EBITDA", "Statements"),
        ]
        required_not_standardized = ["AFFO", "Occupancy", "Same-store NOI", "Lease expirations"]
    elif any(term in industry for term in ("software", "internet content", "information technology services")):
        model = "software"
        label = "Software / recurring revenue"
        metrics_list = [
            _entry("stock_comp_to_revenue", "Stock compensation / revenue", advanced.get("stock_comp_to_revenue"), "percent", "Reported stock compensation / revenue", "Statements"),
            _entry("stock_comp_to_fcf", "Stock compensation / FCF", advanced.get("stock_comp_to_fcf"), "percent", "Reported stock compensation / free cash flow", "Statements"),
            _entry("research_and_development_intensity", "R&D / revenue", advanced.get("research_and_development_intensity"), "percent", "Reported R&D / revenue", "Statements"),
        ]
        required_not_standardized = ["ARR", "Net revenue retention", "Gross retention", "Bookings / billings", "Rule of 40 inputs"]
    elif any(term in industry for term in ("oil", "gas", "energy", "uranium", "coal")) or sector == "energy":
        model = "energy"
        label = "Energy"
        metrics_list = [
            _entry("free_cash_flow", "Free cash flow", (metrics.get("supplemental_metrics") or {}).get("free_cash_flow"), "money", "Operating cash flow less capital spending", "Cash-flow statement"),
            _entry("capex_to_revenue", "Capital spending / revenue", advanced.get("capex_to_revenue"), "percent", "Absolute reported capital expenditure / revenue", "Statements"),
        ]
        required_not_standardized = ["Proved reserves", "Production volume", "Realized commodity prices", "Lifting cost", "Reserve replacement ratio"]
    else:
        metrics_list = [
            _entry("roic", "Return on invested capital", advanced.get("roic"), "percent", "NOPAT / average invested capital", "Statements"),
            _entry("cash_conversion_cycle", "Cash conversion cycle", advanced.get("cash_conversion_cycle"), "days", "DSO + DIO - DPO", "Statements"),
        ]

    # These analyses require detailed note tables, management-defined figures,
    # or a licensed/curated peer history. Listing them explicitly is safer than
    # manufacturing comparables from unrelated companies or treating a missing
    # disclosure as zero.
    global_filing_review = [
        "Debt maturities and covenant headroom",
        "Lease and pension obligation schedules",
        "Segment and geography profitability",
        "GAAP-to-adjusted reconciliation",
        "MD&A drivers and management guidance",
        "Related-party terms and legal-contingency detail",
        "Historical and peer-relative valuation",
    ]
    required_not_standardized = list(dict.fromkeys(required_not_standardized + global_filing_review))

    return {
        "model": model,
        "label": label,
        "metrics": metrics_list,
        "required_not_standardized": required_not_standardized,
        "coverage_note": (
            "Only metrics supported by exact reported inputs are calculated. "
            "Operational and regulatory KPIs that are not standardized in the statement feed remain N/A and must be reviewed in the issuer filing."
        ),
    }
