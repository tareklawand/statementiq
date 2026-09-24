"""Deterministic common-size, change, and trend analysis.

The routines in this module operate only on provider-reported statement rows.
They return ``None`` whenever a denominator or comparison period is missing;
they do not interpolate, annualize, or estimate accounting figures.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd


INCOME_ROWS: Sequence[Tuple[str, Sequence[str]]] = (
    ("Revenue", ("Total Revenue", "Operating Revenue", "Revenue")),
    ("Cost of revenue", ("Cost Of Revenue", "Cost Of Goods Sold", "Reconciled Cost Of Revenue")),
    ("Gross profit", ("Gross Profit",)),
    ("Operating income", ("Operating Income",)),
    ("Pretax income", ("Pretax Income", "Income Before Tax")),
    ("Tax provision", ("Tax Provision", "Income Tax Expense")),
    ("Net income", ("Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations")),
    ("Research & development", ("Research And Development", "Research Development", "Research And Development Expense")),
    ("Interest expense", ("Interest Expense", "Interest Expense Non Operating")),
)

BALANCE_ROWS: Sequence[Tuple[str, Sequence[str]]] = (
    ("Cash & short-term investments", ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial")),
    ("Receivables", ("Receivables", "Accounts Receivable", "Current Receivables")),
    ("Inventory", ("Inventory",)),
    ("Current assets", ("Current Assets", "Total Current Assets")),
    ("Total assets", ("Total Assets",)),
    ("Accounts payable", ("Payables", "Accounts Payable", "Payables And Accrued Expenses")),
    ("Current liabilities", ("Current Liabilities", "Total Current Liabilities")),
    ("Total debt", ("Total Debt",)),
    ("Stockholders' equity", ("Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity")),
)

CASH_FLOW_ROWS: Sequence[Tuple[str, Sequence[str]]] = (
    ("Operating cash flow", ("Operating Cash Flow", "Total Cash From Operating Activities")),
    ("Capital expenditure", ("Capital Expenditure", "Capital Expenditures")),
    ("Free cash flow", ("Free Cash Flow",)),
    ("Stock-based compensation", ("Stock Based Compensation", "Stock-Based Compensation", "Share Based Compensation")),
    ("Cash dividends paid", ("Cash Dividends Paid", "Common Stock Dividend Paid", "Payment Of Dividends")),
    ("Share repurchases", ("Repurchase Of Capital Stock", "Repurchase Of Stock")),
)


def _ordered_columns(df: pd.DataFrame, limit: int) -> List[Any]:
    if df is None or df.empty:
        return []
    try:
        return sorted(df.columns, reverse=True)[:limit]
    except Exception:
        return list(df.columns)[:limit]


def _period_label(column: Any) -> str:
    try:
        return pd.Timestamp(column).strftime("%Y-%m-%d")
    except Exception:
        return str(column)[:10]


def _find_row(df: pd.DataFrame, aliases: Iterable[str]) -> Optional[Any]:
    if df is None or df.empty:
        return None
    index_lookup = {str(index).strip().lower(): index for index in df.index}
    for alias in aliases:
        match = index_lookup.get(alias.strip().lower())
        if match is not None:
            return match
    return None


def _number(df: pd.DataFrame, row: Any, column: Any) -> Optional[float]:
    if row is None:
        return None
    try:
        value = df.loc[row, column]
        return float(value) if pd.notna(value) else None
    except Exception:
        return None


def _change(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    # Percentage change from a zero or negative base is not economically
    # interpretable; keep it N/A rather than publishing a misleading rate.
    if current is None or prior is None or prior <= 0:
        return None
    return current / prior - 1.0


def _analyze_statement(
    df: pd.DataFrame,
    row_definitions: Sequence[Tuple[str, Sequence[str]]],
    denominator_aliases: Optional[Sequence[str]],
    limit: int = 5,
) -> Dict[str, Any]:
    columns = _ordered_columns(df, limit)
    periods = [_period_label(column) for column in columns]
    denominator_row = _find_row(df, denominator_aliases or ()) if denominator_aliases else None
    rows = []
    for label, aliases in row_definitions:
        row = _find_row(df, aliases)
        if row is None:
            continue
        values = [_number(df, row, column) for column in columns]
        common_size: List[Optional[float]] = []
        changes: List[Optional[float]] = []
        for index, (column, value) in enumerate(zip(columns, values)):
            denominator = _number(df, denominator_row, column) if denominator_row is not None else None
            common_size.append(
                value / denominator
                if value is not None and denominator is not None and denominator != 0
                else None
            )
            prior_value = values[index + 1] if index + 1 < len(values) else None
            changes.append(_change(value, prior_value))
        rows.append({
            "metric": label,
            "source_row": str(row),
            "values": values,
            "common_size": common_size,
            "period_over_period_change": changes,
        })
    return {"periods": periods, "rows": rows}


def _quarterly_trends(df: pd.DataFrame, limit: int = 12) -> Dict[str, Any]:
    columns_desc = _ordered_columns(df, limit)
    columns = list(reversed(columns_desc))
    periods = [_period_label(column) for column in columns]
    definitions = (
        ("Revenue", ("Total Revenue", "Operating Revenue", "Revenue")),
        ("Gross profit", ("Gross Profit",)),
        ("Operating income", ("Operating Income",)),
        ("Net income", ("Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations")),
    )
    rows = []
    for label, aliases in definitions:
        row = _find_row(df, aliases)
        if row is None:
            continue
        values = [_number(df, row, column) for column in columns]
        quarter_over_quarter = [
            _change(value, values[index - 1] if index >= 1 else None)
            for index, value in enumerate(values)
        ]
        year_over_year = [
            _change(value, values[index - 4] if index >= 4 else None)
            for index, value in enumerate(values)
        ]
        rows.append({
            "metric": label,
            "source_row": str(row),
            "values": values,
            "quarter_over_quarter_change": quarter_over_quarter,
            "year_over_year_change": year_over_year,
        })
    return {"periods": periods, "rows": rows}


def _large_change_flags(sections: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    flags: List[Dict[str, Any]] = []
    for statement_name, section in sections.items():
        periods = section.get("periods") or []
        for row in section.get("rows") or []:
            changes = row.get("period_over_period_change") or []
            for index, change in enumerate(changes):
                if change is None or abs(change) < 0.25 or index >= len(periods):
                    continue
                flags.append({
                    "statement": statement_name,
                    "metric": row.get("metric"),
                    "period": periods[index],
                    "change": change,
                    "note": "Large period-over-period movement; review the filing and footnotes for the cause.",
                })
    return sorted(flags, key=lambda item: abs(item["change"]), reverse=True)[:12]


def prepare_statement_analysis(
    income_stmt: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    cash_flow: pd.DataFrame,
    quarterly_income_stmt: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    annual = {
        "income_statement": _analyze_statement(
            income_stmt, INCOME_ROWS, ("Total Revenue", "Operating Revenue", "Revenue")
        ),
        "balance_sheet": _analyze_statement(
            balance_sheet, BALANCE_ROWS, ("Total Assets",)
        ),
        "cash_flow": _analyze_statement(cash_flow, CASH_FLOW_ROWS, None),
    }
    return {
        "annual": annual,
        "quarterly_trends": _quarterly_trends(quarterly_income_stmt),
        "large_change_flags": _large_change_flags(annual),
        "methodology": {
            "income_common_size": "Each reported income-statement line divided by reported revenue for the same period.",
            "balance_common_size": "Each reported balance-sheet line divided by reported total assets for the same period.",
            "change": "Current reported period divided by the immediately prior reported period, minus one.",
            "flag_rule": "Absolute annual period-over-period movement of at least 25%; a review flag, not a risk conclusion.",
            "missing_value_policy": "Missing or zero denominators remain N/A. No interpolation or annualization is used.",
        },
    }
