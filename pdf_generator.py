import io
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

def generate_pdf_report(company_name: str, symbol: str, metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> io.BytesIO:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    PRIMARY = colors.HexColor("#0F172A")
    SECONDARY = colors.HexColor("#2563EB")
    SUCCESS = colors.HexColor("#16A34A")
    WARNING = colors.HexColor("#D97706")
    DANGER = colors.HexColor("#DC2626")
    BG_LIGHT = colors.HexColor("#F8FAFC")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=PRIMARY,
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=PRIMARY,
        spaceBefore=7,
        spaceAfter=3
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#1E293B"),
        alignment=TA_JUSTIFY
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=8
    )

    elements = []

    report_generated_at = datetime.utcnow().strftime("%B %d, %Y at %I:%M:%S %p UTC")
    ev_b = metrics.get("ev_breakdown", {})
    market_data_as_of = ev_b.get("market_data_as_of", "Intraday Market Snapshot")
    
    health_score = metrics.get("health_score", 50)

    header_text = Paragraph(f"<b>Financial Health & Valuation Report: {company_name} ({symbol})</b><br/><font size=8.5 color='#2563EB'>Audited Fundamentals with Live Market Valuation</font><br/><font size=6.5 color='#64748B'>Report Generated: {report_generated_at}<br/>Market Data Captured: {market_data_as_of}</font>", title_style)

    score_color = SUCCESS if health_score >= 80 else (WARNING if health_score >= 60 else DANGER)
    score_box_html = f"<font size=16 color='{score_color.hexval()}'><b>{health_score}/100</b></font><br/><font size=6.5 color='#64748B'>Health & Valuation</font>"
    score_p = Paragraph(score_box_html, ParagraphStyle('ScoreP', align=TA_CENTER))

    header_table = Table([[header_text, score_p]], colWidths=[420, 120])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('BACKGROUND', (1,0), (1,0), BG_LIGHT),
        ('BOX', (1,0), (1,0), 1, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (1,0), (1,0), 4),
        ('BOTTOMPADDING', (1,0), (1,0), 4),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=4))

    # Section 1: Audited SEC Financial Facts
    elements.append(Paragraph(f"1. Audited Financial Statements & Balance Sheet Facts ({symbol})", section_heading))
    raw_fin = metrics.get("raw_financials", {})

    def format_money(val):
        if val is None: return "N/A"
        return f"${val / 1e9:,.3f} Billion" if abs(val) >= 1e9 else f"${val / 1e6:,.2f} Million"

    raw_table_data = [
        [
            Paragraph("<b>Financial Metric</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Audited Annual Value</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Statement Provenance Tag</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
        ],
        [Paragraph("Net Sales (Revenue)", body_style), Paragraph(format_money(raw_fin.get("revenue")), body_style), Paragraph(f"{symbol} Income Statement | Total Revenue", body_style)],
        [Paragraph("Gross Margin Dollars", body_style), Paragraph(format_money(raw_fin.get("gross_profit")), body_style), Paragraph(f"{symbol} Income Statement | Gross Profit", body_style)],
        [Paragraph("Operating Income (EBIT)", body_style), Paragraph(format_money(raw_fin.get("operating_income")), body_style), Paragraph(f"{symbol} Income Statement | Operating Income", body_style)],
        [Paragraph("Depreciation & Amortization", body_style), Paragraph(format_money(raw_fin.get("depreciation_amortization")), body_style), Paragraph(f"{symbol} Cash Flow Statement | Depreciation & Amortization", body_style)],
        [Paragraph("Net Income", body_style), Paragraph(format_money(raw_fin.get("net_income")), body_style), Paragraph(f"{symbol} Income Statement | Net Income", body_style)],
        [Paragraph("Current Assets", body_style), Paragraph(format_money(raw_fin.get("current_assets")), body_style), Paragraph(f"{symbol} Balance Sheet | Current Assets", body_style)],
        [Paragraph("Current Liabilities", body_style), Paragraph(format_money(raw_fin.get("current_liabilities")), body_style), Paragraph(f"{symbol} Balance Sheet | Current Liabilities", body_style)],
        [Paragraph("Cash & Short-Term Investments", body_style), Paragraph(format_money(raw_fin.get("cash_and_short_term")), body_style), Paragraph(f"{symbol} Balance Sheet | Cash & Short-Term Investments", body_style)],
        [Paragraph("Total Debt Obligations", body_style), Paragraph(format_money(raw_fin.get("total_debt")), body_style), Paragraph(f"{symbol} Balance Sheet | Total Debt", body_style)],
        [Paragraph("Stockholders Equity", body_style), Paragraph(format_money(raw_fin.get("stockholder_equity")), body_style), Paragraph(f"{symbol} Balance Sheet | Stockholders Equity", body_style)],
    ]

    raw_table = Table(raw_table_data, colWidths=[130, 110, 300])
    raw_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    elements.append(raw_table)
    elements.append(Spacer(1, 6))

    # Section 2: Core Financial Ratios
    elements.append(Paragraph("2. Calculated Financial Ratios with Explicit Weightings & Benchmarks", section_heading))
    ratio_evals = metrics.get("ratio_evaluations", {})

    table_data = [
        [
            Paragraph("<b>Category</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Financial Metric</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Result</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Benchmark Ranges</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Status</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Pts</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Weight</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Score</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
        ]
    ]

    for key, item in ratio_evals.items():
        cat = item.get("category", "")
        name = item.get("name", key)
        val = item.get("value")
        fmt = item.get("format", "{:.2f}")
        target = item.get("target", "")
        status = item.get("status", "N/A")
        pts = item.get("pts", 0.0)
        weight = item.get("weight", 0.10)
        w_pts = item.get("w_pts", 0.0)

        if val is not None:
            val_str = fmt.format(val) if fmt == "{:.1%}" else f"{val:.2f}"
        else:
            val_str = status

        if status == "Healthy":
            status_cell = Paragraph(f"<font color='{SUCCESS.hexval()}'><b>Healthy</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "Caution":
            status_cell = Paragraph(f"<font color='{WARNING.hexval()}'><b>Caution</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "Warning":
            status_cell = Paragraph(f"<font color='{DANGER.hexval()}'><b>Warning</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "N/M":
            status_cell = Paragraph("<font color='#D97706'><b>N/M</b></font>", ParagraphStyle('TD', fontSize=7))
        else:
            status_cell = Paragraph("<font color='#64748B'><b>N/A</b></font>", ParagraphStyle('TD', fontSize=7))

        table_data.append([
            Paragraph(cat, ParagraphStyle('TD', fontSize=7)),
            Paragraph(name, ParagraphStyle('TD', fontSize=7)),
            Paragraph(val_str, ParagraphStyle('TD', fontSize=7, fontName='Helvetica-Bold')),
            Paragraph(target, ParagraphStyle('TD', fontSize=6)),
            status_cell,
            Paragraph(f"{pts:.1f}", ParagraphStyle('TD', fontSize=7)),
            Paragraph(f"{int(weight*100)}%", ParagraphStyle('TD', fontSize=7)),
            Paragraph(f"{w_pts:.1f}", ParagraphStyle('TD', fontSize=7, fontName='Helvetica-Bold'))
        ])

    ratio_table = Table(table_data, colWidths=[55, 140, 45, 145, 55, 30, 40, 30])
    ratio_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    elements.append(ratio_table)
    elements.append(Spacer(1, 6))

    # Section 3: Market Valuation & EV/EBITDA
    elements.append(Paragraph("3. Market Valuation & Enterprise Value Breakdown", section_heading))

    price_val = ev_b.get("share_price")
    price_str = f"${price_val:.2f}" if price_val else "N/A"
    
    eve_val = ev_b.get("ev_ebitda_std")
    eve_str = f"{eve_val:.2f}x" if eve_val else "N/A"

    ev_box_data = [
        [
            Paragraph(f"<b>Market Capitalization:</b> {format_money(ev_b.get('market_cap'))} (Share Price {price_str})", body_style),
            Paragraph(f"<b>Operating Income (EBIT):</b> {format_money(ev_b.get('operating_income'))}", body_style)
        ],
        [
            Paragraph(f"<b>(+) Total Debt Obligations:</b> {format_money(ev_b.get('total_debt'))}", body_style),
            Paragraph(f"<b>(+) Depreciation & Amortization:</b> {format_money(ev_b.get('depreciation_amortization'))}", body_style)
        ],
        [
            Paragraph(f"<b>(-) Cash & Short-Term Investments:</b> {format_money(ev_b.get('cash_and_short_term'))}", body_style),
            Paragraph(f"<b>(=) EBITDA Approximation:</b> <b>{format_money(ev_b.get('ebitda'))}</b>", body_style)
        ],
        [
            Paragraph(f"<b>(=) Enterprise Value:</b> <b>{format_money(ev_b.get('enterprise_value_std'))}</b>", body_style),
            Paragraph(f"<b>(=) Standard EV / EBITDA Multiple:</b> <b>{eve_str}</b>", body_style)
        ]
    ]

    ev_table = Table(ev_box_data, colWidths=[270, 270])
    ev_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    elements.append(ev_table)
    elements.append(Spacer(1, 6))

    # Section 4: AI Qualitative Analysis
    elements.append(Paragraph("4. Executive Briefing & Contextual Financial Drivers", section_heading))
    exec_summary = ai_insights.get("executive_summary", "")
    elements.append(Paragraph(exec_summary, body_style))
    elements.append(Spacer(1, 4))

    strengths = ai_insights.get("top_strengths", [])
    weaknesses = ai_insights.get("top_weaknesses", [])

    str_bullets = [Paragraph("<b>Top Key Strengths</b>", ParagraphStyle('StrHead', fontName='Helvetica-Bold', fontSize=8, textColor=SUCCESS))]
    for s in strengths: str_bullets.append(Paragraph(f"• {s}", bullet_style))

    weak_bullets = [Paragraph("<b>Key Risks & Weaknesses</b>", ParagraphStyle('WeakHead', fontName='Helvetica-Bold', fontSize=8, textColor=DANGER))]
    for w in weaknesses: weak_bullets.append(Paragraph(f"• {w}", bullet_style))

    sw_table = Table([[str_bullets, weak_bullets]], colWidths=[265, 265])
    sw_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#FEF2F2")),
        ('BOX', (0,0), (0,0), 0.5, colors.HexColor("#BBF7D0")),
        ('BOX', (1,0), (1,0), 0.5, colors.HexColor("#FECACA")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(sw_table)

    # Footer note
    elements.append(Spacer(1, 6))
    footer_p = Paragraph(f"<font color='#94A3B8'>StatementIQ Financial Analysis Report for {company_name} ({symbol}). Financial Health Score: {health_score}/100.</font>", ParagraphStyle('Foot', fontName='Helvetica-Oblique', fontSize=6.5, align=TA_CENTER))
    elements.append(footer_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer
