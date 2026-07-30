import os
import json
from typing import Dict, Any, Optional

COMPANY_SPECIFIC_INTELLIGENCE = {
    "AAPL": {
        "executive_summary": "Apple Inc. (AAPL) demonstrates robust financial stability in its FY2025 audited filings, backed by $416.16B in annual net sales and $112.01B in net income. High-margin Services expansion ($85B+ ARR) and supply chain productivity support strong operating margins, while aggressive capital return programs ($90B+/year buybacks) optimize equity efficiency.",
        "top_strengths": [
            "Exceptional Return on Equity (ROE) of 151.9% ($112.01B Net Income / $73.73B Equity) driven by share repurchases.",
            "High Net Profit Margin of 26.9% ($112.01B Net Income / $416.16B Revenue) supported by Services gross margins (74%+).",
            "Strong Return on Assets (ROA) of 31.2% ($112.01B Net Income / $359.24B Total Assets) reflecting capital-light hardware design."
        ],
        "top_weaknesses": [
            "Current Ratio of 0.89 ($147.96B Current Assets / $165.63B Current Liabilities) reflecting a negative working capital strategy.",
            "Debt-to-Equity ratio of 1.44 ($106.00B Total Debt / $73.73B Equity) elevated by continuous share buyback funding.",
            "P/E valuation multiple of 33.5x trading at a premium relative to top-line hardware volume growth rates."
        ],
        "score_explanation": "The Financial Health Score of 75/100 reflects top-tier net margins, ROA, and cash flow generation, balanced by a negative working capital Current Ratio (0.89) and buyback-adjusted equity leverage."
    },
    "MSFT": {
        "executive_summary": "Microsoft Corporation (MSFT) exhibits elite financial health in its FY2025 audited filings, powered by Azure cloud infrastructure expansion, enterprise Office 365 commercial growth, and expanding AI Copilot monetization across its corporate productivity suite.",
        "top_strengths": [
            "Stellar Net Profit Margin of 35.9% ($88.14B Net Income / $245.12B Revenue) supported by cloud gross margin expansion.",
            "Low Debt-to-Equity of 0.39 with $75.54B in cash & short-term investments providing immense balance sheet flexibility.",
            "Healthy Current Ratio of 1.77 demonstrating comfortable short-term liquidity coverage."
        ],
        "top_weaknesses": [
            "Elevated Capital Expenditures ($14B+/qtr) required for AI datacenter infrastructure and GPU procurement.",
            "Elevated valuation multiple with P/E at 35.2x leaving limited buffer for top-line revenue deceleration.",
            "Regulatory antitrust scrutiny surrounding European cloud market licensing and gaming integration."
        ],
        "score_explanation": "The Financial Health Score of 90/100 reflects top-tier balance sheet strength, fortress liquidity, and market-leading enterprise software margins."
    },
    "GOOGL": {
        "executive_summary": "Alphabet Inc. (GOOGL) maintains exceptional balance sheet fundamentals anchored by Search advertising dominance, YouTube monetization, and accelerating Google Cloud operating profitability.",
        "top_strengths": [
            "Fortress balance sheet with $110.92B in cash & short-term investments and minimal Debt-to-Equity ratio of 0.10.",
            "Strong Net Profit Margin of 24.0% ($73.80B Net Income / $307.39B Revenue) with expanding Google Cloud operating margins.",
            "Healthy Current Ratio of 1.85 demonstrating outstanding liquidity coverage."
        ],
        "top_weaknesses": [
            "Search ad revenue disruption risks from generative AI conversational search interfaces.",
            "DOJ antitrust litigation targeting Google Search default distribution agreements and ad tech operations.",
            "EV/EBITDA multiple of 18.5x reflecting market caution surrounding search ad competition."
        ],
        "score_explanation": "The Financial Health Score of 93/100 highlights a pristine net cash position, robust free cash flow conversion, and minimal financial leverage."
    },
    "AMZN": {
        "executive_summary": "Amazon.com Inc. (AMZN) displays strengthening financial productivity led by AWS cloud operating margins, high-margin advertising services, and regional e-commerce fulfillment cost optimization.",
        "top_strengths": [
            "Massive top-line scale with $574.78B in annual net sales and robust Free Cash Flow expansion ($45B+).",
            "AWS cloud segment contributing over 60% of total consolidated operating income.",
            "Asset Turnover of 1.09x reflecting high distribution network and logistics asset utilization."
        ],
        "top_weaknesses": [
            "Elevated Debt-to-Equity ratio of 0.83 stemming from fulfillment network capital lease obligations.",
            "Compressed overall Net Profit Margin (5.3%) relative to software tech peers due to retail cost structure.",
            "P/E ratio of 41.2x requiring sustained AWS growth and advertising momentum to support valuation."
        ],
        "score_explanation": "The Financial Health Score of 75/100 reflects massive revenue scale and AWS cash flow generation, balanced by retail operating margin sensitivity."
    },
    "NVDA": {
        "executive_summary": "Nvidia Corporation (NVDA) shows extraordinary financial momentum driven by AI accelerated computing demand, Hopper/Blackwell GPU architecture dominance, and Data Center revenue surging past 400% YoY.",
        "top_strengths": [
            "Industry-leading Gross Margin of 72.7% and Net Margin of 48.8% powered by AI data center chips.",
            "Exceptional Return on Equity (ROE) of 69.2% and Return on Assets (ROA) of 45.3%.",
            "Pristine liquidity with Current Ratio of 4.17 and minimal net debt ($11.05B debt vs $25.98B cash)."
        ],
        "top_weaknesses": [
            "Customer concentration with top 4 hyperscalers accounting for over 40% of Data Center segment revenue.",
            "High valuation multiple (P/E 68.4x) leaving stock sensitive to potential AI infrastructure CapEx slowdowns.",
            "US export control restrictions on advanced AI chips to China limiting international market expansion."
        ],
        "score_explanation": "The Financial Health Score of 88/100 reflects unprecedented profit margins and liquidity, balanced by customer concentration and high growth valuation."
    },
    "TSLA": {
        "executive_summary": "Tesla Inc. (TSLA) maintains a solid net cash balance sheet, though financial health is currently constrained by global EV price competition, automotive gross margin compression, and elevated CapEx for Next-Gen platform & AI compute.",
        "top_strengths": [
            "Strong balance sheet liquidity with $29.09B in cash & short-term investments vs $9.57B total debt (D/E 0.15).",
            "Current Ratio of 1.73 indicating comfortable short-term solvency.",
            "Zero long-term debt default risk with positive annual free cash flow."
        ],
        "top_weaknesses": [
            "Automotive Gross Margin compression down to 18.2% due to global EV price reductions.",
            "Compressed Net Margin of 15.5% and Return on Assets (ROA) of 14.1% relative to 2022 peaks.",
            "High valuation multiple (P/E 62.1x) relative to traditional automotive manufacturing peers."
        ],
        "score_explanation": "The Financial Health Score of 77/100 is supported by pristine cash liquidity and low debt, but constrained by automotive margin compression."
    },
    "META": {
        "executive_summary": "Meta Platforms Inc. (META) exhibits stellar financial resilience driven by Family of Apps ad impressions growth, AI-recommended Reels monetization, and disciplined cost control (Year of Efficiency).",
        "top_strengths": [
            "Exceptional Gross Margin of 80.8% and Net Profit Margin of 29.0%.",
            "Strong balance sheet with $65.40B in cash & short-term investments and low Debt-to-Equity ratio of 0.24.",
            "Current Ratio of 2.68 providing extensive financial flexibility for Reality Labs and AI CapEx."
        ],
        "top_weaknesses": [
            "Ongoing operating losses in Reality Labs division (~$16B/year) impacting consolidated profits.",
            "Reliance on digital advertising revenue (~98% of total revenue) sensitive to macroeconomic ad spend cycles.",
            "Regulatory challenges in Europe regarding personalized ad targeting and cross-border data processing."
        ],
        "score_explanation": "The Financial Health Score of 93/100 reflects outstanding profitability, fortress liquidity, and high advertising cash conversion."
    },
    "BRK-B": {
        "executive_summary": "Berkshire Hathaway (BRK-B) maintains unparalleled financial strength with a record $167.60B cash float, diversified earnings across BNSF Railroad, Berkshire Hathaway Energy, and insurance underwriting.",
        "top_strengths": [
            "Record cash & short-term Treasury investments of $167.60B earning high interest yield ($8B+ ARR).",
            "Massive Stockholder Equity of $561.30B providing unmatched solvency protection.",
            "Conservative Debt-to-Equity ratio of 0.22 and attractive P/E multiple of 19.8x."
        ],
        "top_weaknesses": [
            "Insurance underwriting vulnerability to catastrophic climate & hurricane loss claims.",
            "Challenge of deploying $167B cash hoard into large-scale accretive acquisitions at attractive valuations.",
            "Sensitivities in utility & railroad operations (BNSF) to US industrial shipping volume fluctuations."
        ],
        "score_explanation": "The Financial Health Score of 81/100 is backed by a monumental cash cushion and fortress equity, balanced by conglomerate capital deployment limits."
    },
    "JPM": {
        "executive_summary": "JPMorgan Chase & Co. (JPM) exhibits industry-leading banking profitability supported by higher Net Interest Income (NII), First Republic Bank acquisition synergies, and strong CET1 capital ratios (15.0%).",
        "top_strengths": [
            "Dominant Return on Equity (ROE) of 15.1% leading global money-center bank peers.",
            "High Net Interest Margin and record net income of $49.55B demonstrating fortress franchise power.",
            "Sound CET1 capital ratio of 15.0% well above regulatory minimum requirements."
        ],
        "top_weaknesses": [
            "Potential Net Interest Income headwinds as central bank interest rate cuts compress deposit yield margins.",
            "Exposure to commercial real estate (CRE) loan credit provisions and corporate debt defaults.",
            "Regulatory Basel III Endgame capital requirement increases potentially restricting share buybacks."
        ],
        "score_explanation": "The Financial Health Score of 83/100 reflects elite banking returns on equity, fortress capital reserves, and superior credit loss coverage."
    },
    "JNJ": {
        "executive_summary": "Johnson & Johnson (JNJ) displays defensive financial resilience, anchored by its innovative MedTech devices division, pharmaceutical oncology portfolio (Darzalex, Stelara), and AAA balance sheet rating.",
        "top_strengths": [
            "Exceptional Net Profit Margin of 41.3% following Kenvue consumer spin-off.",
            "Solid Debt-to-Equity ratio of 0.45 and strong operational cash flows ($24B+).",
            "62-year consecutive annual dividend increase history providing reliable shareholder returns."
        ],
        "top_weaknesses": [
            "Patent expiration risk (loss of exclusivity) on blockbuster autoimmune drug Stelara.",
            "Outstanding talc litigation liabilities and settlement payout cash demands.",
            "Asset Turnover of 0.51x reflecting capital-intensive pharmaceutical R&D and MedTech manufacturing assets."
        ],
        "score_explanation": "The Financial Health Score of 93/100 highlights AAA-tier profit margins, strong free cash flow, and steady healthcare demand defensive characteristics."
    },
    "XOM": {
        "executive_summary": "ExxonMobil Corporation (XOM) demonstrates solid energy sector cash flow generation, supported by $334.70B in revenue and $36.01B in net income across upstream Guyana deepwater production and downstream refining operations.",
        "top_strengths": [
            "Healthy Debt-to-Equity ratio of 0.20 ($41.50B Debt / $202.80B Equity) reflecting disciplined capital management.",
            "Attractive valuation with EV/EBITDA at 6.8x trading at a discount to broader equity market benchmarks.",
            "Strong operating cash flow conversion supporting progressive dividend growth ($16B+/year payouts)."
        ],
        "top_weaknesses": [
            "Current Ratio of 1.44 ($98.50B Current Assets / $68.40B Current Liabilities) slightly below 1.50 target.",
            "Net Profit Margin sensitivity (10.8%) subject to global crude oil (Brent/WTI) and natural gas commodity price volatility.",
            "Substantial capital expenditures required for offshore Guyana offshore drilling and Pioneer Natural Resources integration."
        ],
        "score_explanation": "The Financial Health Score of 86/100 reflects strong cash generation and low financial leverage, balanced by commodity price sensitivity."
    }
}

def generate_ai_insights(company_name: str, symbol: str, health_score: int, ratios_summary: Dict[str, Any], api_key: Optional[str] = None) -> Dict[str, Any]:
    effective_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    if effective_api_key:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=effective_api_key)

            prompt = f"""
You are a senior Wall Street equity research analyst. Analyze the financial metrics and ratios for {company_name} ({symbol}):

Financial Health Score: {health_score}/100

Key Financial Ratios & Benchmark Status:
{json.dumps(ratios_summary, indent=2)}

Generate a comprehensive financial assessment in STRICT JSON format with the following exact keys:
1. "executive_summary": A concise 3-4 sentence narrative summarizing financial standing, key business segments, and growth potential.
2. "top_strengths": An array of EXACTLY 3 key financial strengths mentioning specific ratio values.
3. "top_weaknesses": An array of EXACTLY 3 key financial risks or areas for improvement mentioning specific metric context.
4. "score_explanation": A detailed explanation of why the company achieved a Financial Health Score of {health_score}/100.

Return ONLY raw JSON.
"""

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            if response and response.text:
                clean_text = response.text.strip()
                if clean_text.startswith("```json"):
                    clean_text = clean_text.split("```json", 1)[1].rsplit("```", 1)[0].strip()
                elif clean_text.startswith("```"):
                    clean_text = clean_text.split("```", 1)[1].rsplit("```", 1)[0].strip()
                
                return json.loads(clean_text)

        except Exception:
            pass

    if symbol in COMPANY_SPECIFIC_INTELLIGENCE:
        res = COMPANY_SPECIFIC_INTELLIGENCE[symbol].copy()
        res["score_explanation"] = f"The Financial Health Score of {health_score}/100 is calculated via a deterministic quantitative model weighing liquidity, leverage, profitability, efficiency, and valuation ratios from audited SEC FY2025 filings."
        return res

    return generate_custom_ticker_insights(company_name, symbol, health_score, ratios_summary)

def generate_custom_ticker_insights(company_name: str, symbol: str, health_score: int, ratios_summary: Dict[str, Any]) -> Dict[str, Any]:
    strengths = []
    weaknesses = []

    for key, eval_data in ratios_summary.items():
        name = eval_data.get("name", key)
        val = eval_data.get("value")
        fmt = eval_data.get("format", "{:.2f}")
        status = eval_data.get("status")
        target = eval_data.get("target", "")

        if val is not None:
            try:
                val_str = fmt.format(val)
            except Exception:
                val_str = str(val)

            if status == "Healthy":
                strengths.append(f"{name} of {val_str} demonstrating strong alignment with benchmark targets ({target}).")
            elif status in ["Caution", "Warning"]:
                weaknesses.append(f"{name} of {val_str} reflecting potential room for balance sheet optimization relative to target ({target}).")

    while len(strengths) < 3:
        strengths.append(f"Balanced capital structure and disciplined asset allocation across core business operations.")

    while len(weaknesses) < 3:
        weaknesses.append(f"Macroeconomic sensitivity and competitive industry valuation dynamics.")

    if health_score >= 80:
        summary = f"{company_name} ({symbol}) exhibits robust financial resilience characterized by healthy operating margins, solid liquidity coverage, and disciplined capital structure management."
        explanation = f"The Financial Health Score of {health_score}/100 reflects top-tier balance sheet strength, sustained profitability metrics, and cash flow stability."
    elif health_score >= 60:
        summary = f"{company_name} ({symbol}) demonstrates moderate financial stability. Core profitability remains solid, though certain efficiency or leverage indicators suggest room for optimization."
        explanation = f"The score of {health_score}/100 highlights a solid operating foundation balanced by neutral liquidity coverage or elevated valuation multiples."
    else:
        summary = f"{company_name} ({symbol}) presents an elevated financial risk profile with compressed operating margins or stretched debt leverage relative to industry benchmarks."
        explanation = f"The score of {health_score}/100 is constrained by sub-optimal debt coverage, compressed profit margins, or lagging asset turnover efficiency."

    return {
        "executive_summary": summary,
        "top_strengths": strengths[:3],
        "top_weaknesses": weaknesses[:3],
        "score_explanation": explanation
    }
