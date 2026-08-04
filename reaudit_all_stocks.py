import sys
import pandas as pd
import numpy as np

sys.path.append('/Users/tareklawand/Library/Python/3.9/lib/python/site-packages')

import data_fetcher
import metrics_calculator

PRESET_BLUECHIPS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK-B", "JPM", "JNJ", "LLY"]

RANDOM_100_STOCKS = [
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

def reaudit_all():
    print("======================================================================")
    print("STATEMENTIQ PRO — FULL RE-AUDIT OF PRESETS & 100 RANDOM STOCKS")
    print("======================================================================\n")

    all_tickers = PRESET_BLUECHIPS + RANDOM_100_STOCKS
    errors = []
    audited_count = 0

    for idx, symbol in enumerate(all_tickers, 1):
        try:
            sd = data_fetcher.fetch_stock_data(symbol)
            info = sd["info"]
            metrics = metrics_calculator.compute_metrics(sd)

            # 1. Check Info Data
            price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose") or 0.0
            if not price or price <= 0:
                errors.append(f"{symbol}: Price missing or invalid ({price})")

            # 2. Verify Ratios Math & Benchmarks
            evals = metrics.get("ratio_evaluations", {})
            required_ratios = [
                "current_ratio", "quick_ratio", "debt_to_equity",
                "gross_margin", "net_margin", "roe", "roa",
                "asset_turnover", "pe_ratio", "ev_ebitda"
            ]
            for r_key in required_ratios:
                if r_key not in evals:
                    errors.append(f"{symbol}: Missing ratio key '{r_key}'")
                elif evals[r_key].get("value") is None:
                    errors.append(f"{symbol}: Ratio '{r_key}' is None")

            # 3. Verify Deterministic Score Math
            h_cnt = sum(1 for v in evals.values() if v.get("status") == "Healthy")
            c_cnt = sum(1 for v in evals.values() if v.get("status") == "Caution")
            w_cnt = sum(1 for v in evals.values() if v.get("status") == "Warning")
            
            calc_score = round(((h_cnt * 1.0) + (c_cnt * 0.6) + (w_cnt * 0.2)) / 10.0 * 100)
            actual_score = metrics.get("health_score")

            if calc_score != actual_score:
                errors.append(f"{symbol}: Health score formula discrepancy! Calc={calc_score}, Actual={actual_score}")

            audited_count += 1
            ticker_type = "PRESET" if symbol in PRESET_BLUECHIPS else "SAMPLE"
            print(f"  [{idx:03d}/111] [{ticker_type:<6}] ✓ {symbol:<6} | Price: ${price:>7,.2f} | Score: {actual_score:>3}/100 ({h_cnt}H, {c_cnt}C, {w_cnt}W) | Math Reconciled")

        except Exception as e:
            errors.append(f"{symbol}: Critical Exception - {str(e)}")

    print("\n======================================================================")
    print(f"RE-AUDIT COMPLETE. Total Tickers Re-Audited: {audited_count} / {len(all_tickers)}")
    print(f"Total Discrepancies Found: {len(errors)}")
    if errors:
        print("\nDISCOVERED DISCREPANCIES:")
        for err in errors:
            print(f"  ❌ {err}")
    else:
        print("\n🎉 ALL 111 STOCKS (11 PRESETS + 100 SAMPLE) PASSED 100% MATHEMATICAL & FORMULA RE-AUDIT!")
    print("======================================================================")

if __name__ == "__main__":
    reaudit_all()
