"""Import consolidated, standard US-GAAP facts from official SEC filings.

No issuer-specific financial values, inferred zeroes, segment facts or provider
rows enter these frames. Every populated cell carries its SEC tag, unit, period
and accession. Unsupported/custom taxonomies fail closed to the existing
provider path, where the filing-recency hold remains in force.
"""
from __future__ import annotations

import math
import re
import threading
import time
from collections import OrderedDict
from datetime import date, timedelta
from typing import Any, Dict, Optional

import pandas as pd
import requests

from sec_filing_validator import _headers
from source_limits import read_json

FORMS = {"10-K", "10-K/A", "10-Q", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"}
ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
_CACHE = OrderedDict()
_LOCK = threading.Lock()
_LAST_REQUEST = 0.0
CACHE_TTL = 300

# Aliases have the same accounting meaning. In particular restricted cash,
# net interest, total receivables and aggregate lease/debt tags are NOT aliases
# for unrestricted cash, interest expense, trade receivables or bank debt.
INCOME = {
    "Total Revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "Cost Of Revenue": ("CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"),
    "Gross Profit": ("GrossProfit",),
    "Operating Income": ("OperatingIncomeLoss",),
    "Pretax Income": ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
    "Tax Provision": ("IncomeTaxExpenseBenefit",),
    "Net Income": ("NetIncomeLoss",),
    "Net Income Common Stockholders": ("NetIncomeLossAvailableToCommonStockholdersBasic",),
    "Research And Development": ("ResearchAndDevelopmentExpense",),
    "Selling General And Administration": ("SellingGeneralAndAdministrativeExpense",),
    "Interest Expense": ("InterestExpenseNonOperating", "InterestAndDebtExpense", "InterestExpense"),
    "Diluted EPS": ("EarningsPerShareDiluted",),
    "Basic EPS": ("EarningsPerShareBasic",),
    "Diluted Average Shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
    "Basic Average Shares": ("WeightedAverageNumberOfSharesOutstandingBasic",),
}
BALANCE = {
    "Total Assets": ("Assets",),
    "Current Assets": ("AssetsCurrent",),
    "Current Liabilities": ("LiabilitiesCurrent",),
    "Total Liabilities Net Minority Interest": ("Liabilities",),
    "Total Liabilities And Stockholders Equity": ("LiabilitiesAndStockholdersEquity",),
    "Stockholders Equity": ("StockholdersEquity",),
    "Total Equity Including Noncontrolling Interests": ("StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",),
    "Cash And Cash Equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
    "Other Short Term Investments": ("ShortTermInvestments", "MarketableSecuritiesCurrent", "AvailableForSaleSecuritiesCurrent"),
    "Accounts Receivable": ("AccountsReceivableNetCurrent",),
    "Vendor Nontrade Receivables": ("NontradeReceivablesCurrent",),
    "Inventory": ("InventoryNet",),
    "Accounts Payable": ("AccountsPayableCurrent",),
    "Current Debt": ("DebtCurrent",),
    "Short Term Borrowings": ("ShortTermBorrowings",),
    "Commercial Paper": ("CommercialPaper",),
    "Current Portion Of Long Term Debt": ("LongTermDebtCurrent",),
    "Long Term Debt": ("LongTermDebtNoncurrent",),
    "Total Long Term Debt": ("LongTermDebt",),
    "Retained Earnings": ("RetainedEarningsAccumulatedDeficit",),
    "Goodwill": ("Goodwill",),
    "Net PPE": ("PropertyPlantAndEquipmentNet",),
    "Ordinary Shares Number": ("CommonStockSharesOutstanding",),
}
CASH_FLOW = {
    "Operating Cash Flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "Investing Cash Flow": ("NetCashProvidedByUsedInInvestingActivities",),
    "Financing Cash Flow": ("NetCashProvidedByUsedInFinancingActivities",),
    "Capital Expenditure": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "Depreciation And Amortization": ("DepreciationDepletionAndAmortization",),
    "Stock Based Compensation": ("ShareBasedCompensation",),
    "Cash Dividends Paid": ("PaymentsOfDividends", "PaymentsOfDividendsCommonStock"),
    "Repurchase Of Capital Stock": ("PaymentsForRepurchaseOfCommonStock",),
    "Issuance Of Capital Stock": ("ProceedsFromStockIssuance", "ProceedsFromIssuanceOfCommonStock"),
}


class ImportUnavailable(ValueError):
    pass


def _day(value):
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def get_company_facts(cik: str, accession: str) -> Dict[str, Any]:
    """Bounded single-flight cache; a newly observed accession invalidates it."""
    global _LAST_REQUEST
    key = str(cik).zfill(10)
    with _LOCK:
        now = time.monotonic()
        cached = _CACHE.get(key)
        if cached and cached["accession"] == accession and now - cached["at"] < CACHE_TTL:
            _CACHE.move_to_end(key)
            return cached["payload"]
        delay = .25 - (now - _LAST_REQUEST)
        if delay > 0:
            time.sleep(delay)
        _LAST_REQUEST = time.monotonic()
        response = requests.get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{key}.json",
            headers=_headers(), timeout=(5, 15), stream=True,
        )
        payload = read_json(response)
        if str(payload.get("cik", "")).zfill(10) != key:
            raise ImportUnavailable("SEC facts did not identify the requested registrant.")
        # Company Facts also contains thousands of unrelated footnote tags.
        # Retain only supported concepts so a free 512-MB server does not keep
        # several complete filing histories in memory between analyses.
        supported = {tag for mapping in (INCOME, BALANCE, CASH_FLOW) for tags in mapping.values() for tag in tags}
        concepts = (payload.get("facts") or {}).get("us-gaap") or {}
        payload = {"cik": payload["cik"], "entityName": payload.get("entityName"),
                   "facts": {"us-gaap": {tag: concept for tag, concept in concepts.items() if tag in supported}}}
        _CACHE[key] = {"accession": accession, "at": time.monotonic(), "payload": payload}
        _CACHE.move_to_end(key)
        while len(_CACHE) > 4:
            _CACHE.popitem(last=False)
        return payload


class Facts:
    def __init__(self, payload, filing, currency_hint=None):
        self.filing = filing
        if str(payload.get("cik", "")).zfill(10) != str(filing.get("cik", "")).zfill(10):
            raise ImportUnavailable("SEC facts did not identify the requested registrant.")
        self.target = _day(filing.get("report_period"))
        self.accession = filing.get("accession_number")
        self.concepts = (payload.get("facts") or {}).get("us-gaap") or {}
        if not self.target or not self.accession or not self.concepts:
            raise ImportUnavailable("The latest filing has no supported consolidated US-GAAP facts.")
        if self.target > date.today():
            raise ImportUnavailable("The SEC report period is in the future.")
        currencies = set()
        for tag in INCOME["Net Income"] + INCOME["Total Revenue"]:
            for unit, values in (self.concepts.get(tag, {}).get("units") or {}).items():
                if re.fullmatch(r"[A-Z]{3}", unit) and any(
                    f.get("accn") == self.accession and _day(f.get("end")) == self.target
                    for f in values
                ):
                    currencies.add(unit)
        hint = str(currency_hint or "").upper()
        if hint in currencies:
            self.currency = hint
        elif len(currencies) == 1:
            self.currency = currencies.pop()
        else:
            raise ImportUnavailable("The latest SEC statement currency could not be determined unambiguously.")
        self.provenance = {}
        self.conflicts = []
        self._item_cache = {}
        self._window_cache = {}

    def unit(self, row):
        if "EPS" in row:
            return self.currency + "/shares"
        if "Shares" in row or row == "Ordinary Shares Number":
            return "shares"
        return self.currency

    def items(self, tags, unit):
        cache_key = (tuple(tags), unit)
        if cache_key in self._item_cache:
            return self._item_cache[cache_key]
        items = []
        for rank, tag in enumerate(tags):
            for raw in ((self.concepts.get(tag) or {}).get("units") or {}).get(unit, []):
                if raw.get("form") not in FORMS:
                    continue
                end, start, filed = _day(raw.get("end")), _day(raw.get("start")), _day(raw.get("filed"))
                value = raw.get("val")
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    continue
                if not end or end > self.target or end < self.target - timedelta(days=7 * 366) or not filed or filed > date.today():
                    continue
                items.append({**raw, "tag": tag, "unit": unit, "rank": rank, "_end": end, "_start": start})
        self._item_cache[cache_key] = items
        return items

    def read(self, row, tags, start, end, accession=None):
        items = [f for f in self.items(tags, self.unit(row))
                 if f["_start"] == start and f["_end"] == end
                 and (accession is None or f.get("accn") == accession)]
        if not items:
            return None
        # Most recently filed comparative wins; tag priority resolves true
        # aliases, not distinct contexts. Conflicting duplicate facts are held.
        items.sort(key=lambda f: (f["filed"], -f["rank"]), reverse=True)
        chosen = items[0]
        same = [f for f in items if (f["filed"], f["rank"]) == (chosen["filed"], chosen["rank"])]
        if len({f["val"] for f in same}) > 1:
            self.conflicts.append(f"Conflicting SEC values: {row} at {end}.")
            return None
        return {"value": float(chosen["val"]), "method": "reported", "sources": [{
            "taxonomy": "us-gaap", "tag": chosen["tag"], "unit": chosen["unit"],
            "value": chosen["val"], "coefficient": 1, "start": chosen.get("start"), "end": chosen["end"],
            "accession_number": chosen.get("accn"), "filed": chosen["filed"], "form": chosen["form"],
        }]}

    def windows(self, end, minimum, maximum, annual=False, start=None):
        key = (end, minimum, maximum, annual, start)
        if key in self._window_cache:
            return self._window_cache[key]
        result = set()
        for f in self.items(INCOME["Net Income"] + INCOME["Total Revenue"] + CASH_FLOW["Operating Cash Flow"], self.currency):
            if f["_end"] != end or not f["_start"]:
                continue
            days = (end - f["_start"]).days + 1
            if minimum <= days <= maximum and (not annual or f["form"] in ANNUAL_FORMS) and (start is None or start == f["_start"]):
                result.add((f["_start"], end))
        self._window_cache[key] = sorted(result)
        return self._window_cache[key]

    def flow(self, row, tags, window, latest=False):
        start, end = window
        accession = self.accession if latest and end == self.target else None
        return self.read(row, tags, start, end, accession)

    def quarter(self, row, tags, end):
        direct = self.windows(end, 70, 105)
        if direct:
            value = self.flow(row, tags, direct[0], latest=True)
            if value is not None:
                return value
        # EPS and average share counts are not additive flows. Never subtract
        # annual/YTD EPS or shares to invent a fourth-quarter value.
        if self.unit(row) != self.currency:
            return None
        full = self.windows(end, 70, 385)
        if not full:
            return None
        window = full[0]  # longest disclosed YTD/annual interval
        current = self.flow(row, tags, window, latest=True)
        if current is None:
            return None
        if 70 <= (end - window[0]).days + 1 <= 105:
            return current
        prefix_ends = sorted({f["_end"] for f in self.items(tags, self.unit(row))
                             if f["_start"] == window[0] and 70 <= (end - f["_end"]).days <= 105}, reverse=True)
        for prefix_end in prefix_ends:
            prefix = self.read(row, (current["sources"][0]["tag"],), window[0], prefix_end)
            if prefix is not None:
                return _combine("YTD minus preceding YTD (discrete quarter)", [current, prefix], [1, -1])
        return None

    def ttm(self, row, tags, annual_window):
        end = self.target
        direct = self.windows(end, 330, 385)
        if direct:
            value = self.flow(row, tags, direct[0], latest=True)
            if value is not None:
                return value
        if self.unit(row) != self.currency or annual_window is None:
            return None
        current_windows = self.windows(end, 70, 300)
        if not current_windows:
            return None
        current_window = current_windows[0]
        if current_window[0] != annual_window[1] + timedelta(days=1):
            return None
        current = self.flow(row, tags, current_window, latest=True)
        if current is None:
            return None
        # Do not subtract unlike concepts across an accounting/tag change.
        same_tag = (current["sources"][0]["tag"],)
        annual = self.flow(row, same_tag, annual_window)
        target_days = (end - current_window[0]).days
        prior_ends = {f["_end"] for f in self.items(tags, self.unit(row))
                      if f["_start"] == annual_window[0]
                      and abs((f["_end"] - annual_window[0]).days - target_days) <= 8}
        if len(prior_ends) != 1:
            return None
        prior_end = prior_ends.pop()
        if not 330 <= (end - prior_end).days <= 385:
            return None
        prior = self.read(row, same_tag, annual_window[0], prior_end)
        if current is not None and annual is not None and prior is not None:
            return _combine("prior fiscal year + current YTD - prior comparable YTD (TTM)", [annual, current, prior], [1, 1, -1])
        return None


def _combine(method, cells, factors):
    return {"value": sum(c["value"] * f for c, f in zip(cells, factors)), "method": method,
            "sources": [{**s, "coefficient": s.get("coefficient", 1) * factor}
                        for cell, factor in zip(cells, factors) for s in cell["sources"]]}


def _derive(cells, statement):
    def calculate(row, inputs, factors, method):
        if row not in cells and all(name in cells for name in inputs):
            cells[row] = _combine(method, [cells[name] for name in inputs], factors)
    if statement == "income":
        calculate("Gross Profit", ["Total Revenue", "Cost Of Revenue"], [1, -1], "revenue minus cost of revenue")
    elif statement == "cash_flow":
        for row in ("Capital Expenditure", "Cash Dividends Paid", "Repurchase Of Capital Stock"):
            if row in cells:
                cells[row] = _combine("cash payment shown as a signed cash outflow", [cells[row]], [-1])
        calculate("Free Cash Flow", ["Operating Cash Flow", "Capital Expenditure"], [1, 1], "operating cash flow plus signed capital expenditure")
    else:
        calculate("Cash Cash Equivalents And Short Term Investments", ["Cash And Cash Equivalents", "Other Short Term Investments"], [1, 1], "unrestricted cash plus current investments")
        calculate("Receivables", ["Accounts Receivable", "Vendor Nontrade Receivables"], [1, 1], "trade plus current nontrade receivables")
        short_term = "Short Term Borrowings" if "Short Term Borrowings" in cells else "Commercial Paper"
        calculate("Current Debt", [short_term, "Current Portion Of Long Term Debt"], [1, 1], "short-term borrowings plus current long-term debt")
        calculate("Total Debt", ["Current Debt", "Long Term Debt"], [1, 1], "current debt plus noncurrent long-term debt (excludes leases)")
        # LongTermDebt includes its current portion. Add separately reported
        # short-term borrowing; never add current LTD twice or assume it zero.
        calculate("Total Debt", ["Total Long Term Debt", short_term], [1, 1], "total long-term debt plus short-term borrowings (excludes leases)")
    return cells


def _frame(facts, definitions, periods, statement, frequency, annual_window=None):
    columns = {}
    for window in periods:
        end = window[1]
        cells = {}
        for row, tags in definitions.items():
            if statement == "balance":
                cell = facts.read(row, tags, None, end, facts.accession if end == facts.target else None)
            elif frequency == "quarterly":
                cell = facts.quarter(row, tags, end)
            elif frequency == "ttm":
                cell = facts.ttm(row, tags, annual_window)
            else:
                cell = facts.flow(row, tags, window, latest=True)
            if cell is not None:
                cells[row] = cell
        _derive(cells, statement)
        columns[pd.Timestamp(end)] = {row: cell["value"] for row, cell in cells.items()}
        facts.provenance[f"{frequency}_{statement}:{end.isoformat()}"] = cells
    return pd.DataFrame(columns).sort_index(axis=1, ascending=False).dropna(how="all")


def build_sec_statements(payload: Dict[str, Any], filing: Dict[str, Any], currency_hint=None) -> Dict[str, Any]:
    """Pure transformation, independently testable without network calls."""
    facts = Facts(payload, filing, currency_hint)
    all_ends = {f["_end"] for f in facts.items(INCOME["Net Income"] + INCOME["Total Revenue"], facts.currency)}
    annual_windows = sorted({w for end in all_ends for w in facts.windows(end, 330, 385, annual=True)}, key=lambda w: w[1], reverse=True)[:5]
    quarter_ends = sorted({end for end in all_ends if facts.windows(end, 70, 300) or any(w[1] == end for w in annual_windows)}, reverse=True)[:9]
    annual_latest = next((w for w in annual_windows if w[1] < facts.target), None)
    annual_filing = filing.get("form") in ANNUAL_FORMS
    if annual_filing and not any(w[1] == facts.target for w in annual_windows):
        raise ImportUnavailable("The latest annual filing is not yet present in SEC structured facts.")
    quarters = [(None, end) for end in quarter_ends]
    annual_income = _frame(facts, INCOME, annual_windows, "income", "annual")
    annual_balance = _frame(facts, BALANCE, annual_windows, "balance", "annual")
    annual_cash = _frame(facts, CASH_FLOW, annual_windows, "cash_flow", "annual")
    quarterly_income = _frame(facts, INCOME, quarters, "income", "quarterly")
    quarterly_balance = _frame(facts, BALANCE, quarters, "balance", "quarterly")
    quarterly_cash = _frame(facts, CASH_FLOW, quarters, "cash_flow", "quarterly")
    if annual_filing:
        analysis_income, analysis_cash = annual_income, annual_cash
        basis = "latest_annual"
    else:
        analysis_income = _frame(facts, INCOME, [(None, facts.target)], "income", "ttm", annual_latest)
        analysis_cash = _frame(facts, CASH_FLOW, [(None, facts.target)], "cash_flow", "ttm", annual_latest)
        basis = "trailing_twelve_months"
    balance = annual_balance if annual_filing else quarterly_balance
    def number(df, row):
        try:
            value = df.loc[row, pd.Timestamp(facts.target)]
            return float(value) if pd.notna(value) else None
        except (KeyError, TypeError, ValueError):
            return None
    required = [(analysis_income, "Total Revenue"), (analysis_income, "Net Income"),
                (balance, "Total Assets"), (balance, "Stockholders Equity"), (analysis_cash, "Operating Cash Flow")]
    missing = [row for df, row in required if number(df, row) is None]
    if missing:
        detail = " ".join(dict.fromkeys(facts.conflicts))
        raise ImportUnavailable("Latest SEC facts lack a complete, period-aligned core dataset: " + ", ".join(missing) + ". " + detail)
    checks = []
    assets = number(balance, "Total Assets")
    total = number(balance, "Total Liabilities And Stockholders Equity")
    liabilities = number(balance, "Total Liabilities Net Minority Interest")
    equity = number(balance, "Total Equity Including Noncontrolling Interests")
    # Without consolidated equity, parent equity cannot be substituted when
    # noncontrolling interests may exist. The explicit balance total is safest.
    if total is not None:
        checks.append({"check": "assets = liabilities and equity", "difference": assets - total})
    elif liabilities is not None and equity is not None:
        checks.append({"check": "assets = liabilities + consolidated equity", "difference": assets - liabilities - equity})
    if not checks:
        raise ImportUnavailable("SEC balance-sheet reconciliation inputs are missing.")
    for check in checks:
        check["matched"] = abs(check["difference"]) <= max(abs(assets) * .0005, 1.0)
    if assets <= 0 or not all(c["matched"] for c in checks):
        raise ImportUnavailable("The latest SEC balance-sheet reconciliation failed.")
    revenue, cost, gross = (number(analysis_income, row) for row in ("Total Revenue", "Cost Of Revenue", "Gross Profit"))
    if cost is not None and gross is not None:
        difference = revenue - cost - gross
        matched = abs(difference) <= max(abs(revenue) * .0005, 1.0)
        checks.append({"check": "gross profit = revenue - cost of revenue", "difference": difference, "matched": matched})
        if not matched:
            raise ImportUnavailable("The latest SEC income-statement reconciliation failed.")
    populated = sum(len(cells) for key, cells in facts.provenance.items() if key.endswith(facts.target.isoformat()))
    return {
        "status": "imported", "source": "SEC Company Facts", "currency": facts.currency,
        "report_period": facts.target.isoformat(), "accession_number": facts.accession,
        "filing_url": filing.get("filing_url"), "basis": basis,
        "populated_cell_count": populated, "integrity_checks": checks,
        "debt_basis": "Borrowings excluding lease liabilities; a missing debt component is not assumed to be zero.",
        "provenance": facts.provenance, "warnings": list(dict.fromkeys(facts.conflicts)),
        "frames": {
            "income_stmt": annual_income, "balance_sheet": annual_balance, "cash_flow": annual_cash,
            "quarterly_income_stmt": quarterly_income, "quarterly_balance_sheet": quarterly_balance,
            "quarterly_cash_flow": quarterly_cash, "analysis_income_stmt": analysis_income,
            "analysis_balance_sheet": balance, "analysis_cash_flow": analysis_cash,
        },
    }


def import_latest_sec_statements(filing, currency_hint=None):
    if filing.get("status") != "verified":
        return {"status": "not_applicable", "reason": "No verified SEC registrant and periodic filing were available."}
    try:
        payload = get_company_facts(filing["cik"], filing["accession_number"])
        return build_sec_statements(payload, filing, currency_hint)
    except Exception as exc:
        return {"status": "unavailable", "source": "SEC Company Facts", "reason": str(exc)}
