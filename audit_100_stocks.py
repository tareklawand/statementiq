import sys
import pandas as pd
import numpy as np

sys.path.append('/Users/tareklawand/Library/Python/3.9/lib/python/site-packages')

import data_fetcher
import metrics_calculator
import pdf_generator

STOCKS_100 = [
    "AMD", "INTC", "ORCL", "CRM", "CSCO", "ADBE", "TXN", "QCOM", "AVGO", "ACN",
    "IBM", "NOW", "UBER", "ABNB", "PFE", "MRK", "ABBV", "UNH", "BMY", "AMGN",
    "GILD", "CVS", "CI", "ISRG", "VRTX", "REGN", "MDT", "DHR", "SYK", "BSX",
    "TMO", "ZTS", "ELV", "HUM", "BA", "CAT", "DE", "GE", "HON", "LMT",
    "RTX", "UNP", "UPS", "FDX", "EMR", "ETN", "ITW", "PH", "GD", "NOC",
    "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "HES",
    "WMT", "COST", "PG", "KO", "PEP", "PM", "MO", "CL", "MDLZ", "TGT",
    "HD", "LOW", "NKE", "MCD", "SBUX", "TJX", "BKNG", "ORLY", "AZO", "MAR",
    "V", "MA", "BAC", "WFC", "C", "GS", "MS", "AXP", "BLK", "SCHW",
    "DIS", "NFLX", "TMUS", "VZ", "T", "CMCSA", "NEE", "DUK", "SO", "PLD"
]

def run_100_stocks_audit():
    print("======================================================================")
    print(f"STATEMENTIQ PRO — 100 NON-PRESET GLOBAL STOCKS COMPREHENSIVE AUDIT")
    print("======================================================================\n")

    errors_found = []
    audited_count = 0

    results_table = []

    for idx, symbol in enumerate(STOCKS_100, 1):
        try:
            sd = data_fetcher.fetch_stock_data(symbol)
            info = sd["info"]
            metrics = metrics_calculator.compute_metrics(sd)
            
            sector = info.get("sector") or "N/A"
            industry = info.get("industry") or "N/A"
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose") or 0.0
            mkt_cap = info.get("marketCap") or 0.0
            
            # Verify basic info
            if not sector or sector == "N/A":
                errors_found.append(f"{symbol}: Sector missing or N/A")
            if not price or price == 0.0:
                errors_found.append(f"{symbol}: Missing price")
                
            # Verify 10 ratio evaluations
            evals = metrics["ratio_evaluations"]
            expected_keys = [
                "current_ratio", "quick_ratio", "debt_to_equity", 
                "gross_margin", "net_margin", "roe", "roa", 
                "asset_turnover", "pe_ratio", "ev_ebitda"
            ]
            for k in expected_keys:
                if k not in evals:
                    errors_found.append(f"{symbol}: Missing ratio {k}")
                elif evals[k].get("value") is None:
                    errors_found.append(f"{symbol}: Null value for ratio {k}")

            # Verify Deterministic Health Score Math
            healthy_count = sum(1 for v in evals.values() if v.get("status") == "Healthy")
            caution_count = sum(1 for v in evals.values() if v.get("status") == "Caution")
            warning_count = sum(1 for v in evals.values() if v.get("status") == "Warning")
            
            expected_score = round(((healthy_count * 1.0) + (caution_count * 0.6) + (warning_count * 0.2)) / 10.0 * 100)
            actual_score = metrics["health_score"]
            
            if expected_score != actual_score:
                errors_found.append(f"{symbol}: Score mismatch! Expected {expected_score}, got {actual_score}")

            audited_count += 1
            results_table.append({
                "index": idx,
                "symbol": symbol,
                "name": info.get("longName") or info.get("shortName") or symbol,
                "sector": sector,
                "price": price,
                "market_cap_b": mkt_cap / 1e9,
                "health_score": actual_score,
                "healthy": healthy_count,
                "caution": caution_count,
                "warning": warning_count
            })

            print(f"  [{idx:03d}/100] ✓ {symbol:<6} | {sector:<24} | Price: ${price:>7,.2f} | Cap: ${mkt_cap/1e9:>7,.1f}B | Score: {actual_score:>3}/100 ({healthy_count}H, {caution_count}C, {warning_count}W)")

        except Exception as e:
            errors_found.append(f"{symbol}: Audit exception - {str(e)}")

    print("\n======================================================================")
    print(f"AUDIT COMPLETE. Total Non-Preset Tickers Audited: {audited_count} / {len(STOCKS_100)}")
    print(f"Total Errors Discovered: {len(errors_found)}")
    if errors_found:
        print("\nDISCOVERED AUDIT ERRORS:")
        for err in errors_found:
            print(f"  - {err}")
    else:
        print("\n🎉 ALL 100 DIVERSE GLOBAL STOCKS PASSED 100% AUDIT RECONCILIATION!")
    print("======================================================================")

    # Save Markdown Audit Summary to scratch
    df_res = pd.DataFrame(results_table)
    df_res.to_csv("audit_100_stocks_results.csv", index=False)
    print(f"Results saved to audit_100_stocks_results.csv")

if __name__ == "__main__":
    run_100_stocks_audit()
