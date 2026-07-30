import io
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

def generate_pdf_report(company_name: str, symbol: str, metrics: Dict[str, Any], ai_insights: Dict[str, Any]) -> io.BytesIO:
    """
    Generates a PDF report using ReportLab and returns it as a BytesIO stream.
    """
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

    # Custom Palette
    PRIMARY = colors.HexColor("#0F172A")    # Dark slate header
    SECONDARY = colors.HexColor("#2563EB")  # Accent blue
    SUCCESS = colors.HexColor("#16A34A")    # Green
    WARNING = colors.HexColor("#D97706")    # Yellow/Amber
    DANGER = colors.HexColor("#DC2626")     # Red
    BG_LIGHT = colors.HexColor("#F8FAFC")

    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY,
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#64748B"),
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#1E293B"),
        alignment=TA_JUSTIFY
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B"),
        leftIndent=12
    )

    elements = []

    # Title & Header Table
    current_date = datetime.now().strftime("%B %d, %Y")
    health_score = metrics.get("health_score", 50)
    health_status = metrics.get("health_status", "N/A")

    header_text = Paragraph(f"<b>Financial Analysis Report: {company_name} ({symbol})</b>", title_style)
    sub_text = Paragraph(f"Generated on {current_date} | Automated AI Financial Assessment", subtitle_style)

    # Score Badge cell content
    score_color = SUCCESS if health_score >= 80 else (WARNING if health_score >= 60 else DANGER)
    score_box_html = f"<font size=16 color='{score_color.hexval()}'><b>{health_score}/100</b></font><br/><font size=8 color='#64748B'>Health Score</font>"
    score_p = Paragraph(score_box_html, ParagraphStyle('ScoreP', align=TA_CENTER))

    header_table = Table([[header_text, score_p]], colWidths=[420, 120])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('BACKGROUND', (1,0), (1,0), BG_LIGHT),
        ('BOX', (1,0), (1,0), 1, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (1,0), (1,0), 6),
        ('BOTTOMPADDING', (1,0), (1,0), 6),
    ]))
    
    elements.append(header_table)
    elements.append(sub_text)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0"), spaceBefore=2, spaceAfter=10))

    # Executive Summary
    elements.append(Paragraph("Executive Summary & AI Insights", section_heading))
    exec_summary = ai_insights.get("executive_summary", "Financial analysis summary unavailable.")
    elements.append(Paragraph(exec_summary, body_style))
    elements.append(Spacer(1, 8))

    # Score Explanation
    score_exp = ai_insights.get("score_explanation", "")
    if score_exp:
        elements.append(Paragraph(f"<b>Financial Health Drivers:</b> {score_exp}", body_style))
        elements.append(Spacer(1, 8))

    # Strengths & Weaknesses (2-column layout)
    strengths = ai_insights.get("top_strengths", [])
    weaknesses = ai_insights.get("top_weaknesses", [])

    str_bullets = [Paragraph("<b>Top Key Strengths</b>", ParagraphStyle('StrHead', fontName='Helvetica-Bold', fontSize=10, textColor=SUCCESS))]
    for s in strengths:
        str_bullets.append(Paragraph(f"• {s}", bullet_style))

    weak_bullets = [Paragraph("<b>Key Risks & Weaknesses</b>", ParagraphStyle('WeakHead', fontName='Helvetica-Bold', fontSize=10, textColor=DANGER))]
    for w in weaknesses:
        weak_bullets.append(Paragraph(f"• {w}", bullet_style))

    sw_table = Table([[str_bullets, weak_bullets]], colWidths=[265, 265])
    sw_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (0,0), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#FEF2F2")),
        ('BOX', (0,0), (0,0), 0.5, colors.HexColor("#BBF7D0")),
        ('BOX', (1,0), (1,0), 0.5, colors.HexColor("#FECACA")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(sw_table)
    elements.append(Spacer(1, 14))

    # 10 Financial Ratios Table
    elements.append(Paragraph("Core 10 Financial Ratios & Benchmark Analysis", section_heading))

    ratio_evals = metrics.get("ratio_evaluations", {})

    table_data = [
        [
            Paragraph("<b>Category</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, textColor=PRIMARY)),
            Paragraph("<b>Financial Metric</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, textColor=PRIMARY)),
            Paragraph("<b>Value</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, textColor=PRIMARY)),
            Paragraph("<b>Benchmark</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, textColor=PRIMARY)),
            Paragraph("<b>Status</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8.5, textColor=PRIMARY)),
        ]
    ]

    for key, item in ratio_evals.items():
        cat = item.get("category", "")
        name = item.get("name", key)
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

        # Status text color
        if status == "Healthy":
            status_cell = Paragraph(f"<font color='{SUCCESS.hexval()}'><b>Healthy</b></font>", ParagraphStyle('TD', fontSize=8.5))
        elif status == "Caution":
            status_cell = Paragraph(f"<font color='{WARNING.hexval()}'><b>Caution</b></font>", ParagraphStyle('TD', fontSize=8.5))
        elif status == "Warning":
            status_cell = Paragraph(f"<font color='{DANGER.hexval()}'><b>Warning</b></font>", ParagraphStyle('TD', fontSize=8.5))
        else:
            status_cell = Paragraph("N/A", ParagraphStyle('TD', fontSize=8.5))

        table_data.append([
            Paragraph(cat, ParagraphStyle('TD', fontSize=8.5)),
            Paragraph(name, ParagraphStyle('TD', fontSize=8.5)),
            Paragraph(val_str, ParagraphStyle('TD', fontSize=8.5, fontName='Helvetica-Bold')),
            Paragraph(target, ParagraphStyle('TD', fontSize=8.5)),
            status_cell
        ])

    ratio_table = Table(table_data, colWidths=[90, 175, 85, 90, 90])
    ratio_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BG_LIGHT),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))

    elements.append(ratio_table)
    elements.append(Spacer(1, 14))

    # Raw Financial Highlights
    elements.append(Paragraph("Key Raw Financial Overview (Latest Fiscal Year)", section_heading))
    raw_fin = metrics.get("raw_financials", {})

    def format_money(val):
        if val is None: return "N/A"
        return f"${val / 1e9:,.2f} Billion" if abs(val) >= 1e9 else f"${val / 1e6:,.2f} Million"

    fin_summary_data = [
        [
            Paragraph("<b>Total Revenue:</b> " + format_money(raw_fin.get("revenue")), body_style),
            Paragraph("<b>Net Income:</b> " + format_money(raw_fin.get("net_income")), body_style)
        ],
        [
            Paragraph("<b>Total Assets:</b> " + format_money(raw_fin.get("total_assets")), body_style),
            Paragraph("<b>Total Debt:</b> " + format_money(raw_fin.get("total_debt")), body_style)
        ],
        [
            Paragraph("<b>Cash & Equivalents:</b> " + format_money(raw_fin.get("cash_and_equiv")), body_style),
            Paragraph("<b>Stockholder Equity:</b> " + format_money(raw_fin.get("stockholder_equity")), body_style)
        ]
    ]

    fin_table = Table(fin_summary_data, colWidths=[265, 265])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(fin_table)

    # Footer note
    elements.append(Spacer(1, 16))
    footer_p = Paragraph(f"<font color='#94A3B8'>Disclaimer: This report is automatically generated for informational purposes only. Past performance does not guarantee future results.</font>", ParagraphStyle('Foot', fontName='Helvetica-Oblique', fontSize=7.5, align=TA_CENTER))
    elements.append(footer_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer
