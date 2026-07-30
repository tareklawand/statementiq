import streamlit as st
import pandas as pd
import numpy as np
import os

from data_fetcher import fetch_stock_data, PRESET_TICKERS
from metrics_calculator import compute_metrics
from ai_analyst import generate_ai_insights
from charts import (
    plot_health_score_gauge,
    plot_revenue_net_income,
    plot_cash_vs_debt,
    plot_margins_trend
)
from pdf_generator import generate_pdf_report

# Page Configuration
st.set_page_config(
    page_title="StatementIQ PRO | Corporate Financial Analysis & Valuation Platform",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Google Stitch Aesthetic Design System
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>
    /* Global Canvas & Ambient Radial Gradient */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    }
    
    .stApp {
        background-color: #07090E !important;
        background-image: radial-gradient(circle at 50% 0%, rgba(56, 189, 248, 0.12) 0%, rgba(7, 9, 14, 0) 70%),
                          radial-gradient(circle at 100% 50%, rgba(99, 102, 241, 0.08) 0%, rgba(7, 9, 14, 0) 50%) !important;
        background-attachment: fixed !important;
        color: #F8FAFC !important;
    }

    /* Sidebar Glassmorphism */
    section[data-testid="stSidebar"] {
        background: rgba(10, 14, 24, 0.92) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
        backdrop-filter: blur(20px) !important;
    }
    
    /* Header blur */
    header[data-testid="stHeader"] {
        background: rgba(7, 9, 14, 0.7) !important;
        backdrop-filter: blur(16px) !important;
    }
    
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
        width: 6px;
        height: 6px;
    }
    ::-webkit-scrollbar-track {
        background: #07090E;
    }
    ::-webkit-scrollbar-thumb {
        background: #1E293B;
        border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: #00F2FE;
    }

    /* Top Ticker Ribbon Banner */
    .terminal-hero {
        background: rgba(13, 18, 30, 0.75) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px 28px !important;
        margin-bottom: 24px !important;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
        position: relative;
        overflow: hidden;
    }

    .terminal-hero::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00F2FE 0%, #38BDF8 50%, #6366F1 100%);
    }

    .ticker-symbol-badge {
        background: linear-gradient(135deg, #38BDF8 0%, #6366F1 100%) !important;
        color: #FFFFFF !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 800 !important;
        font-size: 0.95rem !important;
        padding: 4px 12px !important;
        border-radius: 8px !important;
        letter-spacing: 0.05em !important;
        display: inline-block;
        box-shadow: 0 2px 10px rgba(56, 189, 248, 0.3) !important;
    }

    .company-title-text {
        font-family: 'Outfit', sans-serif !important;
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        color: #FFFFFF !important;
        margin: 0 !important;
        letter-spacing: -0.02em !important;
    }

    .hero-meta-row {
        display: flex;
        align-items: center;
        gap: 14px;
        color: #94A3B8;
        font-size: 0.9rem;
        margin-top: 6px;
    }

    /* Key Metric Stat Cards */
    .kpi-card {
        background: rgba(13, 18, 30, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 18px !important;
        position: relative;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25) !important;
        transition: all 0.25s ease !important;
    }
    
    .kpi-card:hover {
        border-color: rgba(56, 189, 248, 0.4) !important;
        box-shadow: 0 8px 24px rgba(56, 189, 248, 0.2) !important;
        transform: translateY(-2px) !important;
    }

    .kpi-val {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 1.6rem !important;
        font-weight: 800 !important;
        color: #F8FAFC !important;
        margin-top: 4px !important;
    }

    .kpi-lbl {
        font-size: 0.72rem !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        color: #64748B !important;
        font-weight: 800 !important;
    }

    /* Glassmorphic Panel */
    .glass-panel {
        background: rgba(13, 18, 30, 0.75) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        margin-bottom: 24px !important;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.5) !important;
    }

    /* AI Executive Briefing Container */
    .ai-briefing-card {
        background: rgba(13, 18, 30, 0.75) !important;
        backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        position: relative;
        box-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.5) !important;
    }

    .ai-badge {
        background: rgba(0, 242, 254, 0.12) !important;
        color: #00F2FE !important;
        border: 1px solid rgba(0, 242, 254, 0.3) !important;
        padding: 5px 14px !important;
        border-radius: 20px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.8rem !important;
        font-weight: 800 !important;
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }

    /* Strength & Risk Item Cards */
    .strength-item-card {
        background: rgba(16, 185, 129, 0.06) !important;
        border: 1px solid rgba(16, 185, 129, 0.25) !important;
        border-left: 5px solid #10B981 !important;
        border-radius: 10px !important;
        padding: 14px 18px !important;
        margin-bottom: 12px !important;
        font-size: 0.92rem !important;
        color: #F8FAFC !important;
        line-height: 1.55 !important;
    }

    .risk-item-card {
        background: rgba(239, 68, 68, 0.06) !important;
        border: 1px solid rgba(239, 68, 68, 0.25) !important;
        border-left: 5px solid #EF4444 !important;
        border-radius: 10px !important;
        padding: 14px 18px !important;
        margin-bottom: 12px !important;
        font-size: 0.92rem !important;
        color: #F8FAFC !important;
        line-height: 1.55 !important;
    }

    /* Ratio Metric Card with Visual Progress Bar */
    .ratio-card {
        background: rgba(13, 18, 30, 0.75) !important;
        backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 14px !important;
        padding: 20px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.25s ease !important;
    }

    .ratio-card:hover {
        border-color: rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px) !important;
    }

    .ratio-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    .status-healthy {
        background: rgba(16, 185, 129, 0.15) !important;
        color: #10B981 !important;
        border: 1px solid rgba(16, 185, 129, 0.35) !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 0.75rem !important;
        font-weight: 800 !important;
    }

    .status-caution {
        background: rgba(245, 158, 11, 0.15) !important;
        color: #F59E0B !important;
        border: 1px solid rgba(245, 158, 11, 0.35) !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 0.75rem !important;
        font-weight: 800 !important;
    }

    .status-warning {
        background: rgba(239, 68, 68, 0.15) !important;
        color: #EF4444 !important;
        border: 1px solid rgba(239, 68, 68, 0.35) !important;
        padding: 4px 12px !important;
        border-radius: 20px !important;
        font-size: 0.75rem !important;
        font-weight: 800 !important;
    }

    .progress-bar-bg {
        height: 6px;
        width: 100%;
        background: rgba(6, 9, 15, 0.8);
        border-radius: 4px;
        margin-top: 12px;
        overflow: hidden;
    }

    .progress-bar-fill-green {
        height: 100%;
        background: linear-gradient(90deg, #10B981, #34D399);
        border-radius: 4px;
    }

    .progress-bar-fill-amber {
        height: 100%;
        background: linear-gradient(90deg, #F59E0B, #FBBF24);
        border-radius: 4px;
    }

    .progress-bar-fill-red {
        height: 100%;
        background: linear-gradient(90deg, #EF4444, #F87171);
        border-radius: 4px;
    }

    /* Tabs Override */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        background-color: rgba(13, 18, 30, 0.75) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        color: #94A3B8 !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        padding: 0 22px !important;
        transition: all 0.25s ease !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #6366F1 0%, #00F2FE 100%) !important;
        color: #FFFFFF !important;
        border-color: transparent !important;
        box-shadow: 0 4px 16px rgba(0, 242, 254, 0.35) !important;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar Branding & Search
st.sidebar.markdown("""
<div style='text-align: center; padding-bottom: 16px;'>
    <div style='font-family: Outfit, sans-serif; font-size: 1.5rem; font-weight: 800; color: #FFFFFF; letter-spacing: -0.01em;'>
        Statement<span style='color: #00F2FE;'>IQ</span> <span style='background: linear-gradient(135deg, #6366F1, #8B5CF6); color: #FFF; font-size: 0.65rem; font-weight: 800; padding: 2px 7px; border-radius: 5px; vertical-align: super;'>PRO</span>
    </div>
    <div style='font-size: 0.68rem; color: #64748B; font-weight: 700; letter-spacing: 0.08em; margin-top: 4px;'>
        INSTITUTIONAL FINANCIAL ANALYSIS & RATIO BENCHMARKING
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("<h4 style='font-size: 0.78rem; text-transform: uppercase; color: #64748B; font-weight: 800; letter-spacing: 0.06em;'>COVERED TICKERS</h4>", unsafe_allow_html=True)

selection_mode = st.sidebar.radio("Ticker Selection", ["Featured Bluechips", "Search Custom Ticker"], index=0)

if selection_mode == "Featured Bluechips":
    preset_choice = st.sidebar.selectbox("Select Target Company", list(PRESET_TICKERS.keys()))
    symbol = PRESET_TICKERS[preset_choice]
else:
    custom_symbol = st.sidebar.text_input("Enter Ticker Symbol (e.g. AAPL, MSFT, LLY, COST)", value="AAPL")
    symbol = custom_symbol.strip().upper()

st.sidebar.markdown("---")
st.sidebar.markdown("<h4 style='font-size: 0.78rem; text-transform: uppercase; color: #64748B; font-weight: 800; letter-spacing: 0.06em;'>GEMINI AI PRO ENGINE</h4>", unsafe_allow_html=True)
api_key_input = st.sidebar.text_input(
    "Gemini API Key (Optional)", 
    type="password",
    help="Provide Google Gemini API Key for real-time LLM structured analysis. If omitted, heuristic analytics rule engine operates automatically."
)

# Fetch Stock Data
if not symbol:
    st.warning("Please enter a valid stock ticker symbol.")
    st.stop()

with st.spinner(f"Connecting to market feed & fetching financials for {symbol}..."):
    stock_data = fetch_stock_data(symbol)

if stock_data.get("error"):
    st.error(stock_data["error"])
    st.stop()

info = stock_data["info"]
company_name = info.get("longName") or info.get("shortName") or symbol
sector = info.get("sector", "Healthcare" if symbol in ["LLY", "PFE", "MRK", "UNH"] else "General Industry")
industry = info.get("industry", "Drug Manufacturers - General" if symbol in ["LLY", "PFE", "MRK"] else "General Business")
current_price = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
market_cap = info.get("marketCap")
pe_ratio = info.get("trailingPE") or info.get("forwardPE")
currency = info.get("currency", "USD")
fifty_two_high = info.get("fiftyTwoWeekHigh")
fifty_two_low = info.get("fiftyTwoWeekLow")
target_price = info.get("targetMeanPrice")

# Top Header Hero Banner
st.markdown(f"""
<div class='terminal-hero'>
    <div style='display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;'>
        <div>
            <div style='display: flex; align-items: center; gap: 14px;'>
                <h1 class='company-title-text'>{company_name}</h1>
                <span class='ticker-symbol-badge'>{symbol}</span>
            </div>
            <div class='hero-meta-row'>
                <span>Sector: <b style='color: #F8FAFC;'>{sector}</b></span>
                <span>•</span>
                <span>Industry: <b style='color: #F8FAFC;'>{industry}</b></span>
                <span>•</span>
                <span>Currency: <b style='color: #00F2FE;'>{currency}</b></span>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Key Performance Indicator Row
c_st1, c_st2, c_st3, c_st4 = st.columns(4)

with c_st1:
    price_str = f"${current_price:,.2f}" if current_price else "N/A"
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-lbl'>Share Price</div>
        <div class='kpi-val' style='color: #00F2FE;'>{price_str}</div>
    </div>
    """, unsafe_allow_html=True)

with c_st2:
    mkt_str = f"${market_cap / 1e9:,.2f}B" if market_cap else "N/A"
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-lbl'>Market Capitalization</div>
        <div class='kpi-val'>{mkt_str}</div>
    </div>
    """, unsafe_allow_html=True)

with c_st3:
    pe_str = f"{pe_ratio:.2f}x" if pe_ratio else "N/A"
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-lbl'>P/E Ratio (Trailing)</div>
        <div class='kpi-val'>{pe_str}</div>
    </div>
    """, unsafe_allow_html=True)

with c_st4:
    target_str = f"${target_price:,.2f}" if target_price else "N/A"
    st.markdown(f"""
    <div class='kpi-card'>
        <div class='kpi-lbl'>Analyst Target Price</div>
        <div class='kpi-val' style='color: #10B981;'>{target_str}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-bottom: 24px;'></div>", unsafe_allow_html=True)

# Compute Metrics & Health Score
metrics = compute_metrics(stock_data)

# Generate AI Insights
with st.spinner("Processing ratio audit & executing AI evaluation engine..."):
    ai_insights = generate_ai_insights(
        company_name=company_name,
        symbol=symbol,
        health_score=metrics["health_score"],
        ratios_summary=metrics["ratio_evaluations"],
        api_key=api_key_input
    )

# PDF Generation Download in Sidebar
try:
    pdf_buffer = generate_pdf_report(company_name, symbol, metrics, ai_insights)
    st.sidebar.markdown("---")
    st.sidebar.markdown("<h4 style='font-size: 0.78rem; text-transform: uppercase; color: #64748B; font-weight: 800; letter-spacing: 0.06em;'>EXECUTIVE REPORT EXPORT</h4>", unsafe_allow_html=True)
    st.sidebar.download_button(
        label="📥 Download PDF Audit Summary",
        data=pdf_buffer,
        file_name=f"{symbol}_Executive_Financial_Report.pdf",
        mime="application/pdf",
        use_container_width=True
    )
except Exception as e:
    st.sidebar.error(f"PDF compilation error: {e}")

# 3 Main Dashboard Tabs
tab1, tab2, tab3 = st.tabs([
    "🎯 Tab 1: Executive AI Briefing & Performance Trends",
    "📊 Tab 2: 10 Fundamental Financial Ratios",
    "📑 Tab 3: Audited Financial Statements"
])

# ==================== TAB 1: AI INSIGHTS & CHARTS ====================
with tab1:
    col_score, col_summary = st.columns([1, 2])
    
    with col_score:
        st.markdown("<div class='glass-panel'>", unsafe_allow_html=True)
        st.markdown("<div style='text-align: center; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.08em; color: #64748B; text-transform: uppercase;'>DETERMINISTIC FINANCIAL HEALTH SCORECARD</div>", unsafe_allow_html=True)
        fig_gauge = plot_health_score_gauge(metrics["health_score"])
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        status_color = "#10B981" if metrics["health_score"] >= 80 else ("#F59E0B" if metrics["health_score"] >= 60 else "#EF4444")
        st.markdown(f"<div style='text-align: center; font-weight: 800; font-size: 1.2rem; color: {status_color}; font-family: Outfit, sans-serif;'>{metrics['health_status'].upper()}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_summary:
        st.markdown("<div class='ai-briefing-card'>", unsafe_allow_html=True)
        st.markdown("<div style='display: flex; justify-content: space-between; align-items: center;'><span class='ai-badge'>🤖 GEMINI ANALYST BRIEFING</span></div>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 0.98rem; line-height: 1.65; color: #F8FAFC; margin-top: 14px;'>{ai_insights.get('executive_summary', '')}</p>", unsafe_allow_html=True)
        st.markdown("<hr style='border-color: rgba(255, 255, 255, 0.08); margin: 16px 0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size: 0.75rem; font-weight: 800; color: #64748B; text-transform: uppercase; letter-spacing: 0.06em;'>SCORE DETERMINATION DRIVERS</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='font-size: 0.92rem; color: #94A3B8; margin-top: 6px;'>{ai_insights.get('score_explanation', '')}</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin-top: 24px;'></div>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-family: Outfit, sans-serif; font-weight: 800;'>📌 Strategic Investment Strengths & Key Risks</h3>", unsafe_allow_html=True)
    col_str, col_weak = st.columns(2)

    with col_str:
        st.markdown("<h5 style='color: #10B981; font-family: Outfit, sans-serif; font-weight: 800;'>✅ Top 3 Key Strengths</h5>", unsafe_allow_html=True)
        for strength in ai_insights.get("top_strengths", []):
            st.markdown(f"<div class='strength-item-card'><b>•</b> {strength}</div>", unsafe_allow_html=True)

    with col_weak:
        st.markdown("<h5 style='color: #EF4444; font-family: Outfit, sans-serif; font-weight: 800;'>⚠️ Top 3 Key Risks / Weaknesses</h5>", unsafe_allow_html=True)
        for weakness in ai_insights.get("top_weaknesses", []):
            st.markdown(f"<div class='risk-item-card'><b>•</b> {weakness}</div>", unsafe_allow_html=True)

    st.markdown("<hr style='border-color: rgba(255, 255, 255, 0.08); margin: 28px 0;'>", unsafe_allow_html=True)
    st.markdown("<h3 style='font-family: Outfit, sans-serif; font-weight: 800;'>📊 Core Trend Analytics</h3>", unsafe_allow_html=True)
    
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        fig_rev = plot_revenue_net_income(stock_data["income_stmt"])
        st.plotly_chart(fig_rev, use_container_width=True)

    with c_chart2:
        fig_cd = plot_cash_vs_debt(stock_data["balance_sheet"])
        st.plotly_chart(fig_cd, use_container_width=True)

    c_chart3, _ = st.columns([1, 1])
    with c_chart3:
        fig_margin = plot_margins_trend(stock_data["income_stmt"])
        st.plotly_chart(fig_margin, use_container_width=True)

# ==================== TAB 2: 10 FINANCIAL RATIOS ====================
with tab2:
    st.markdown("<h3 style='font-family: Outfit, sans-serif; font-weight: 800;'>🔢 Categorized 10 Financial Ratio Audit</h3>", unsafe_allow_html=True)
    st.caption("Each metric is benchmarked against standard healthy corporate thresholds with progress indicators.")

    ratio_evals = metrics["ratio_evaluations"]

    def render_ratio_card(item: dict):
        name = item.get("name", "")
        cat = item.get("category", "")
        val = item.get("value")
        fmt = item.get("format", "{:.2f}")
        target = item.get("target", "")
        status = item.get("status", "N/A")

        if val is not None:
            try:
                val_str = fmt.format(val)
            except Exception:
                val_str = str(val)
        else:
            val_str = "N/A"

        if status == "Healthy":
            status_html = f"<span class='status-healthy'>● HEALTHY (Target {target})</span>"
            fill_class = "progress-bar-fill-green"
            fill_pct = 90
        elif status == "Caution":
            status_html = f"<span class='status-caution'>● CAUTION (Target {target})</span>"
            fill_class = "progress-bar-fill-amber"
            fill_pct = 60
        elif status == "Warning":
            status_html = f"<span class='status-warning'>● WARNING (Target {target})</span>"
            fill_class = "progress-bar-fill-red"
            fill_pct = 30
        else:
            status_html = f"<span class='status-caution'>N/A</span>"
            fill_class = "progress-bar-fill-amber"
            fill_pct = 0

        st.markdown(f"""
        <div class='ratio-card'>
            <div class='ratio-header'>
                <span style='font-size: 0.72rem; font-weight: 800; color: #64748B; text-transform: uppercase;'>{cat}</span>
                {status_html}
            </div>
            <div style='color: #94A3B8; font-size: 0.9rem; font-weight: 700;'>{name}</div>
            <div style='font-family: JetBrains Mono, monospace; font-size: 1.8rem; font-weight: 800; color: #F8FAFC; margin-top: 4px;'>{val_str}</div>
            <div class='progress-bar-bg'>
                <div class='{fill_class}' style='width: {fill_pct}%;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Categories Layout
    st.markdown("<h4 style='color: #00F2FE; font-family: Outfit, sans-serif; font-size: 1.15rem; font-weight: 800; margin-top: 10px;'>1. Liquidity & Financial Flexibility</h4>", unsafe_allow_html=True)
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        render_ratio_card(ratio_evals.get("current_ratio", {}))
    with col_l2:
        render_ratio_card(ratio_evals.get("quick_ratio", {}))

    st.markdown("<h4 style='color: #00F2FE; font-family: Outfit, sans-serif; font-size: 1.15rem; font-weight: 800; margin-top: 10px;'>2. Capital Structure & Leverage</h4>", unsafe_allow_html=True)
    col_lev1, _ = st.columns([1, 1])
    with col_lev1:
        render_ratio_card(ratio_evals.get("debt_to_equity", {}))

    st.markdown("<h4 style='color: #00F2FE; font-family: Outfit, sans-serif; font-size: 1.15rem; font-weight: 800; margin-top: 10px;'>3. Profitability & Returns</h4>", unsafe_allow_html=True)
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        render_ratio_card(ratio_evals.get("gross_margin", {}))
    with col_p2:
        render_ratio_card(ratio_evals.get("net_margin", {}))
    with col_p3:
        render_ratio_card(ratio_evals.get("roe", {}))
    with col_p4:
        render_ratio_card(ratio_evals.get("roa", {}))

    st.markdown("<h4 style='color: #00F2FE; font-family: Outfit, sans-serif; font-size: 1.15rem; font-weight: 800; margin-top: 10px;'>4. Efficiency & Asset Management</h4>", unsafe_allow_html=True)
    col_e1, _ = st.columns([1, 3])
    with col_e1:
        render_ratio_card(ratio_evals.get("asset_turnover", {}))

    st.markdown("<h4 style='color: #00F2FE; font-family: Outfit, sans-serif; font-size: 1.15rem; font-weight: 800; margin-top: 10px;'>5. Valuation Multiples</h4>", unsafe_allow_html=True)
    col_v1, col_v2 = st.columns(2)
    with col_v1:
        render_ratio_card(ratio_evals.get("pe_ratio", {}))
    with col_v2:
        render_ratio_card(ratio_evals.get("ev_ebitda", {}))

# ==================== TAB 3: RAW FINANCIAL STATEMENTS ====================
with tab3:
    st.markdown("<h3 style='font-family: Outfit, sans-serif; font-weight: 800;'>📑 Audited Financial Statements</h3>", unsafe_allow_html=True)
    st.caption("Inspect multi-year primary financial statements sourced directly from SEC filings via `yfinance`.")

    stmt_type = st.radio("Select Financial Statement", ["Income Statement", "Balance Sheet", "Cash Flow"], horizontal=True)

    if stmt_type == "Income Statement":
        df_stmt = stock_data["income_stmt"]
    elif stmt_type == "Balance Sheet":
        df_stmt = stock_data["balance_sheet"]
    else:
        df_stmt = stock_data["cash_flow"]

    if df_stmt is not None and not df_stmt.empty:
        df_display = df_stmt.copy()
        df_display.columns = [pd.to_datetime(c).strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c) for c in df_display.columns]
        
        search_term = st.text_input("🔎 Search row in statement", placeholder="e.g. Revenue, Operating Income, Cash...")
        if search_term:
            filtered_idx = [idx for idx in df_display.index if search_term.lower() in str(idx).lower()]
            df_display = df_display.loc[filtered_idx]

        st.dataframe(
            df_display.style.format(lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and not np.isnan(x) else ("-" if pd.isna(x) else str(x))),
            use_container_width=True,
            height=540
        )
    else:
        st.warning(f"No {stmt_type} data available for {symbol}.")
