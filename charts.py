import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from typing import Dict, Any

# Elite Dark Palette & Glassmorphic Transparency
DARK_CANVAS = "#07090E"
CARD_BG = "rgba(0,0,0,0)"
CARD_BORDER = "rgba(255, 255, 255, 0.08)"
TEXT_MAIN = "#F8FAFC"
TEXT_MUTED = "#94A3B8"

COLOR_CYAN = "#00F2FE"
COLOR_EMERALD = "#10B981"
COLOR_BLUE = "#38BDF8"
COLOR_INDIGO = "#6366F1"
COLOR_PURPLE = "#8B5CF6"
COLOR_AMBER = "#F59E0B"
COLOR_CRIMSON = "#EF4444"

def plot_health_score_gauge(score: int) -> go.Figure:
    """Creates a high-end radial gauge chart for Financial Health Score."""
    if score >= 80:
        accent = COLOR_EMERALD
    elif score >= 60:
        accent = COLOR_AMBER
    else:
        accent = COLOR_CRIMSON

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={'x': [0, 1], 'y': [0, 1]},
        number={
            'suffix': " / 100",
            'font': {'size': 42, 'color': TEXT_MAIN, 'family': "Outfit, sans-serif", 'weight': 800}
        },
        gauge={
            'axis': {
                'range': [0, 100],
                'tickwidth': 1.5,
                'tickcolor': TEXT_MUTED,
                'dtick': 20,
                'tickfont': {'size': 11, 'color': TEXT_MUTED}
            },
            'bar': {'color': accent, 'thickness': 0.85},
            'bgcolor': "rgba(10, 14, 24, 0.6)",
            'borderwidth': 1,
            'bordercolor': CARD_BORDER,
            'steps': [
                {'range': [0, 60], 'color': "rgba(239, 68, 68, 0.12)"},
                {'range': [60, 80], 'color': "rgba(245, 158, 11, 0.12)"},
                {'range': [80, 100], 'color': "rgba(16, 185, 129, 0.12)"}
            ],
        }
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': TEXT_MAIN, 'family': "Plus Jakarta Sans, sans-serif"},
        margin=dict(l=20, r=20, t=20, b=10),
        height=220
    )
    return fig

def plot_revenue_net_income(income_stmt: pd.DataFrame) -> go.Figure:
    """Generates 4-year Revenue Bar & Net Income Area Trend chart."""
    fig = go.Figure()

    if income_stmt is not None and not income_stmt.empty:
        cols = list(income_stmt.columns)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]
        
        rev_vals = []
        ni_vals = []
        index_lower = [str(i).strip().lower() for i in income_stmt.index]
        
        for c in cols:
            r = None
            for name in ["Total Revenue", "Operating Revenue", "Revenue"]:
                if name.lower() in index_lower:
                    r = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    break
            
            ni = None
            for name in ["Net Income", "Net Income Common Stockholders", "Net Income Continuous Operations"]:
                if name.lower() in index_lower:
                    ni = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    break
                    
            rev_vals.append(float(r) / 1e9 if pd.notna(r) else 0.0)
            ni_vals.append(float(ni) / 1e9 if pd.notna(ni) else 0.0)

        # Revenue Bar
        fig.add_trace(go.Bar(
            x=years,
            y=rev_vals,
            name="Total Revenue ($B)",
            marker=dict(
                color="rgba(56, 189, 248, 0.75)",
                line=dict(color=COLOR_BLUE, width=1.5),
                cornerradius=6
            ),
            hovertemplate="<b>%{x} Revenue</b><br>$%{y:.2f} Billion<extra></extra>"
        ))
        
        # Net Income Glow Area
        fig.add_trace(go.Scatter(
            x=years,
            y=ni_vals,
            name="Net Income ($B)",
            mode="lines+markers",
            fill='tozeroy',
            fillcolor='rgba(16, 185, 129, 0.15)',
            line=dict(color=COLOR_EMERALD, width=3.5, shape='spline'),
            marker=dict(size=8, color=COLOR_EMERALD, symbol="circle", line=dict(color="#000", width=1.5)),
            hovertemplate="<b>%{x} Net Income</b><br>$%{y:.2f} Billion<extra></extra>"
        ))

    fig.update_layout(
        title=dict(
            text="<span style='font-weight:800; color:#F8FAFC;'>Revenue Growth & Profitability</span> <span style='font-weight:400; color:#94A3B8; font-size:13px;'>(4-Year Trend)</span>",
            font=dict(size=15, family="Outfit, sans-serif")
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT_MAIN, family="Plus Jakarta Sans, sans-serif"),
        xaxis=dict(showgrid=False, linecolor=CARD_BORDER, tickfont=dict(color=TEXT_MUTED, size=11)),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            gridwidth=1,
            title=dict(text="USD ($ Billions)", font=dict(color=TEXT_MUTED, size=11)),
            tickfont=dict(color=TEXT_MUTED, size=11)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=11, color=TEXT_MAIN),
            bgcolor="rgba(0,0,0,0)"
        ),
        margin=dict(l=45, r=25, t=55, b=35),
        height=340
    )
    return fig

def plot_cash_vs_debt(balance_sheet: pd.DataFrame) -> go.Figure:
    """Generates Cash vs Total Debt comparison chart."""
    fig = go.Figure()

    if balance_sheet is not None and not balance_sheet.empty:
        cols = list(balance_sheet.columns)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]

        cash_vals = []
        debt_vals = []
        index_lower = [str(i).strip().lower() for i in balance_sheet.index]

        for c in cols:
            cash = None
            for name in ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments", "Cash Financial"]:
                if name.lower() in index_lower:
                    cash = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    break

            debt = None
            for name in ["Total Debt", "Long Term Debt", "Current Debt"]:
                if name.lower() in index_lower:
                    debt = balance_sheet.loc[balance_sheet.index[index_lower.index(name.lower())], c]
                    break

            cash_vals.append(float(cash) / 1e9 if pd.notna(cash) else 0.0)
            debt_vals.append(float(debt) / 1e9 if pd.notna(debt) else 0.0)

        fig.add_trace(go.Bar(
            x=years,
            y=cash_vals,
            name="Cash & Equivalents",
            marker=dict(color="rgba(16, 185, 129, 0.85)", line=dict(color=COLOR_EMERALD, width=1.5), cornerradius=6),
            hovertemplate="<b>%{x} Cash</b><br>$%{y:.2f} Billion<extra></extra>"
        ))

        fig.add_trace(go.Bar(
            x=years,
            y=debt_vals,
            name="Total Debt Obligations",
            marker=dict(color="rgba(239, 68, 68, 0.85)", line=dict(color=COLOR_CRIMSON, width=1.5), cornerradius=6),
            hovertemplate="<b>%{x} Debt</b><br>$%{y:.2f} Billion<extra></extra>"
        ))

    fig.update_layout(
        title=dict(
            text="<span style='font-weight:800; color:#F8FAFC;'>Balance Sheet Liquidity</span> <span style='font-weight:400; color:#94A3B8; font-size:13px;'>(Cash vs Debt)</span>",
            font=dict(size=15, family="Outfit, sans-serif")
        ),
        barmode='group',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT_MAIN, family="Plus Jakarta Sans, sans-serif"),
        xaxis=dict(showgrid=False, linecolor=CARD_BORDER, tickfont=dict(color=TEXT_MUTED, size=11)),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            gridwidth=1,
            title=dict(text="USD ($ Billions)", font=dict(color=TEXT_MUTED, size=11)),
            tickfont=dict(color=TEXT_MUTED, size=11)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=11, color=TEXT_MAIN),
            bgcolor="rgba(0,0,0,0)"
        ),
        margin=dict(l=45, r=25, t=55, b=35),
        height=340
    )
    return fig

def plot_margins_trend(income_stmt: pd.DataFrame) -> go.Figure:
    """Generates Gross Margin vs Net Margin line trend chart."""
    fig = go.Figure()

    if income_stmt is not None and not income_stmt.empty:
        cols = list(income_stmt.columns)[:4]
        cols = sorted(cols)
        years = [pd.to_datetime(c).strftime('%Y') if hasattr(c, 'strftime') else str(c)[:4] for c in cols]

        gross_margins = []
        net_margins = []
        index_lower = [str(i).strip().lower() for i in income_stmt.index]

        for c in cols:
            rev = None
            for name in ["Total Revenue", "Operating Revenue", "Revenue"]:
                if name.lower() in index_lower:
                    rev = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    break
            
            gp = None
            for name in ["Gross Profit"]:
                if name.lower() in index_lower:
                    gp = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    break
                    
            ni = None
            for name in ["Net Income", "Net Income Common Stockholders"]:
                if name.lower() in index_lower:
                    ni = income_stmt.loc[income_stmt.index[index_lower.index(name.lower())], c]
                    break
                    
            if pd.notna(rev) and float(rev) != 0:
                gm_val = (float(gp) / float(rev)) * 100 if pd.notna(gp) else 0.0
                nm_val = (float(ni) / float(rev)) * 100 if pd.notna(nm) if pd.notna(ni) else 0.0
            else:
                gm_val, nm_val = 0.0, 0.0
                
            gross_margins.append(gm_val)
            net_margins.append(nm_val)

        fig.add_trace(go.Scatter(
            x=years,
            y=gross_margins,
            name="Gross Margin (%)",
            mode="lines+markers",
            line=dict(color=COLOR_PURPLE, width=3.5, shape='spline'),
            marker=dict(size=8, color=COLOR_PURPLE),
            hovertemplate="<b>%{x} Gross Margin</b><br>%{y:.1f}%<extra></extra>"
        ))

        fig.add_trace(go.Scatter(
            x=years,
            y=net_margins,
            name="Net Margin (%)",
            mode="lines+markers",
            line=dict(color=COLOR_AMBER, width=3.5, shape='spline'),
            marker=dict(size=8, color=COLOR_AMBER),
            hovertemplate="<b>%{x} Net Margin</b><br>%{y:.1f}%<extra></extra>"
        ))

    fig.update_layout(
        title=dict(
            text="<span style='font-weight:800; color:#F8FAFC;'>Operating Margin Dynamics</span> <span style='font-weight:400; color:#94A3B8; font-size:13px;'>(Gross vs Net Margin)</span>",
            font=dict(size=15, family="Outfit, sans-serif")
        ),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=TEXT_MAIN, family="Plus Jakarta Sans, sans-serif"),
        xaxis=dict(showgrid=False, linecolor=CARD_BORDER, tickfont=dict(color=TEXT_MUTED, size=11)),
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.06)",
            gridwidth=1,
            title=dict(text="Percentage (%)", font=dict(color=TEXT_MUTED, size=11)),
            tickfont=dict(color=TEXT_MUTED, size=11)
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="right",
            x=1,
            font=dict(size=11, color=TEXT_MAIN),
            bgcolor="rgba(0,0,0,0)"
        ),
        margin=dict(l=45, r=25, t=55, b=35),
        height=340
    )
    return fig
