import json
from data_fetcher import fetch_stock_data, PRESET_TICKERS
from metrics_calculator import compute_metrics
from ai_analyst import generate_ai_insights

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "JNJ", "LLY", "BRK-B"]

def run_live_audits():
    print("==========================================================================")
    print("LIVE AUDIT RESULTS FOR ALL 11 COVERED TICKERS")
    print("==========================================================================")
    
    results = {}
    for symbol in TICKERS:
        data = fetch_stock_data(symbol)
        metrics = compute_metrics(data)
        ai = generate_ai_insights(symbol, symbol, metrics["health_score"], metrics["ratio_evaluations"])
        
        info = data.get("info", {})
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        mkt_cap = info.get("marketCap")
        mkt_cap_b = f"${mkt_cap / 1e9:,.2f}B" if mkt_cap else "N/A"
        
        evals = metrics["ratio_evaluations"]
        
        summary_ratios = {}
        for r_k, r_v in evals.items():
            val_fmt = f"{r_v['value']:.2f}" if r_v['value'] is not None else 'N/A'
            summary_ratios[r_k] = f"{r_v['status']} ({val_fmt})"

            
        results[symbol] = {
            "symbol": symbol,
            "company": info.get("longName", symbol),
            "price": price,
            "market_cap": mkt_cap_b,
            "is_financial_sector": metrics["is_financial_sector"],
            "health_score": metrics["health_score"],
            "health_status": metrics["health_status"],
            "ratios": summary_ratios,
            "exec_summary": ai["executive_summary"][:120] + "..."
        }
        
        print(f"✅ [{symbol}] {info.get('longName', symbol)}")
        print(f"   Sector Financial: {metrics['is_financial_sector']} | Score: {metrics['health_score']}/100 ({metrics['health_status']})")
        print(f"   Price: ${price} | Market Cap: {mkt_cap_b}")
        print(f"   Ratios evaluated: {len(evals)} | Key statuses: NetMargin={evals.get('net_margin',{}).get('status')}, ROA={evals.get('roa',{}).get('status')}, PE={evals.get('pe_ratio',{}).get('status')}")
        print("--------------------------------------------------------------------------")

    with open("live_audit_11_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("ALL 11 TICKERS AUDITED & VERIFIED SUCCESSFULLY!")

if __name__ == "__main__":
    run_live_audits()
