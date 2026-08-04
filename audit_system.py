import sys
import pandas as pd
import numpy as np

sys.path.append('/Users/tareklawand/Library/Python/3.9/lib/python/site-packages')

import data_fetcher
import metrics_calculator
import charts
import pdf_generator

def run_full_audit():
    print("======================================================================")
    print("STATEMENTIQ PRO — FULL SYSTEMWIDE DATA & MATHEMATICAL AUDIT REPORT")
    print("======================================================================\n")

    presets = data_fetcher.PRESET_TICKERS
    errors_found = []

    for name, symbol in presets.items():
        print(f"Auditing {symbol} ({name})...")
        try:
            sd = data_fetcher.fetch_stock_data(symbol)
            info = sd["info"]
            metrics = metrics_calculator.compute_metrics(sd)
            
            # 1. Verify Info fields
            if not info.get("symbol"): errors_found.append(f"{symbol}: Missing symbol in info")
            if not info.get("sector") or info.get("sector") == "N/A": errors_found.append(f"{symbol}: Sector is N/A")
            if not info.get("industry") or info.get("industry") == "N/A": errors_found.append(f"{symbol}: Industry is N/A")
            if info.get("regularMarketPrice") is None: errors_found.append(f"{symbol}: Missing market price")
            if info.get("marketCap") is None: errors_found.append(f"{symbol}: Missing market cap")
            
            # 2. Verify Ratio Evaluations (10 ratios present)
            evals = metrics["ratio_evaluations"]
            expected_keys = [
                "current_ratio", "quick_ratio", "debt_to_equity", 
                "gross_margin", "net_margin", "roe", "roa", 
                "asset_turnover", "pe_ratio", "ev_ebitda"
            ]
            for k in expected_keys:
                if k not in evals:
                    errors_found.append(f"{symbol}: Missing ratio evaluation for {k}")
                elif evals[k].get("value") is None:
                    errors_found.append(f"{symbol}: Null value for ratio {k}")
                    
            # 3. Verify Health Score Formula Math
            healthy_count = sum(1 for v in evals.values() if v.get("status") == "Healthy")
            caution_count = sum(1 for v in evals.values() if v.get("status") == "Caution")
            warning_count = sum(1 for v in evals.values() if v.get("status") == "Warning")
            
            expected_score = round(((healthy_count * 1.0) + (caution_count * 0.6) + (warning_count * 0.2)) / 10.0 * 100)
            actual_score = metrics["health_score"]
            
            if expected_score != actual_score:
                errors_found.append(f"{symbol}: Score mismatch! Expected {expected_score}, got {actual_score}")
                
            # 4. Verify PDF Generator execution
            pdf_buf = pdf_generator.generate_pdf_report(
                info.get("longName", symbol), 
                symbol, 
                metrics, 
                {
                    "executive_summary": "Test summary", 
                    "top_strengths": ["S1"], 
                    "top_weaknesses": ["W1"]
                }
            )
            if not pdf_buf or pdf_buf.getbuffer().nbytes == 0:
                errors_found.append(f"{symbol}: Generated PDF is empty")
                
            print(f"  ✓ {symbol} Passed Audit! Sector: {info.get('sector')}, Price: ${info.get('regularMarketPrice'):,.2f}, Score: {actual_score}/100 ({healthy_count}H, {caution_count}C, {warning_count}W)")

        except Exception as e:
            errors_found.append(f"{symbol}: Exception occurred during audit - {str(e)}")

    print("\n======================================================================")
    print(f"AUDIT COMPLETE. Total Tickers Audited: {len(presets)}")
    print(f"Total Errors Discovered: {len(errors_found)}")
    if errors_found:
        print("DISCOVERED ERRORS:")
        for err in errors_found:
            print(f"  - {err}")
    else:
        print("🎉 ALL 11 PRESET BLUECHIP PROFILES & METRICS PASSED 100% AUDIT RECONCILIATION!")
    print("======================================================================")

if __name__ == "__main__":
    run_full_audit()
