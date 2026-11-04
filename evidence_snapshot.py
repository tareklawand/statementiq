"""Build reproducible SEC-only evidence, separately from market-data rights."""
from datetime import datetime, timezone

from data_fetcher import _is_financial_institution, _sec_sic_profile
from sec_filing_validator import get_latest_sec_filing
from sec_statement_importer import import_latest_sec_statements


def capture_sec_evidence(symbol):
    filing = get_latest_sec_filing(symbol, force_refresh=True)
    imported = import_latest_sec_statements(filing)
    if imported.get("status") != "imported":
        return {"error": imported.get("reason") or "A complete supported SEC statement dataset was unavailable."}
    info = {"symbol": symbol, "longName": filing.get("registrant"),
            "financialCurrency": imported["currency"], "statement_data_provider": "SEC Company Facts",
            "market_data_provider": None, "data_source": "official_sec_evidence", **_sec_sic_profile(filing)}
    basis = {"income": imported["basis"], "cash_flow": imported["basis"],
             "balance_sheet": "latest_annual" if imported["basis"] == "latest_annual" else "latest_quarter"}
    basis.update({key + "_period_end": imported["report_period"] for key in ("income", "balance_sheet", "cash_flow")})
    return {"symbol": symbol, "info": info, "error": None, **imported["frames"],
            "is_financial_sector": _is_financial_institution(info), "analysis_basis": basis,
            "sec_filing": filing, "sec_statement_import": {k: v for k, v in imported.items() if k != "frames"},
            "fetched_at": datetime.now(timezone.utc).isoformat(), "integrity_hold_reason": None,
            "sec_fact_validation": {"status": "direct_import", "checks": imported["integrity_checks"],
                                    "checked": len(imported["integrity_checks"]), "matched": len(imported["integrity_checks"])},
            "verification_scope": "Selected SEC consolidated US-GAAP facts with source tags, arithmetic and reconciliation checks. Not an independent audit.",
            "quality_warnings": imported.get("warnings") or []}
