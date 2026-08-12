import pytest
import io
from pdf_generator import generate_pdf_report

def test_pdf_generation_multiple_tickers():
    tickers = ["AAPL", "MSFT", "JPM", "NVDA"]
    
    for symbol in tickers:
        metrics = {
            "health_score": 75,
            "ev_breakdown": {
                "market_cap": 2500e9,
                "share_price": 220.0,
                "operating_income": 80e9,
                "depreciation_amortization": 10e9,
                "ebitda": 90e9,
                "total_debt": 50e9,
                "cash_and_short_term": 60e9,
                "enterprise_value_std": 2490e9,
                "ev_ebitda_std": 27.67,
                "market_data_as_of": "Intraday Market Snapshot"
            },
            "raw_financials": {
                "revenue": 300e9,
                "gross_profit": 140e9,
                "operating_income": 80e9,
                "depreciation_amortization": 10e9,
                "net_income": 70e9,
                "current_assets": 120e9,
                "current_liabilities": 90e9,
                "cash_and_short_term": 60e9,
                "total_debt": 50e9,
                "stockholder_equity": 150e9
            },
            "ratio_evaluations": {
                "net_margin": {"name": "Net Margin", "category": "Profitability", "value": 0.233, "status": "Healthy", "target": "Healthy ≥ 15%", "format": "{:.1%}", "pts": 1.0, "weight": 0.10, "w_pts": 10.0},
                "current_ratio": {"name": "Current Ratio", "category": "Liquidity", "value": 1.33, "status": "Caution", "target": "Healthy ≥ 1.50", "format": "{:.2f}", "pts": 0.6, "weight": 0.10, "w_pts": 6.0}
            }
        }
        
        ai_insights = {
            "executive_summary": f"Executive summary test report for {symbol}.",
            "top_strengths": [f"{symbol} strength 1", f"{symbol} strength 2"],
            "top_weaknesses": [f"{symbol} risk 1", f"{symbol} risk 2"]
        }
        
        buf = generate_pdf_report(f"{symbol} Corporation", symbol, metrics, ai_insights)
        assert isinstance(buf, io.BytesIO)
        pdf_bytes = buf.getvalue()
        assert len(pdf_bytes) > 1000 # PDF generated successfully
        assert pdf_bytes.startswith(b"%PDF")
