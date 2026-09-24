import io
from datetime import datetime
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY

def generate_pdf_report(
    company_name: str,
    symbol: str,
    metrics: Dict[str, Any],
    ai_insights: Dict[str, Any],
    data_quality: Optional[Dict[str, Any]] = None,
) -> io.BytesIO:
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
    market_data_as_of = ev_b.get("market_data_as_of") or "Unavailable"
    market_currency = ev_b.get("market_currency") or ""
    statement_currency = ev_b.get("statement_currency") or market_currency
    data_quality = data_quality or {}
    basis = data_quality.get("analysis_basis") or metrics.get("analysis_basis") or {}
    sec_filing = data_quality.get("sec_filing") or {}
    sec_fact_validation = data_quality.get("sec_fact_validation") or {}
    calculation_coverage = data_quality.get("calculation_coverage") or metrics.get("calculation_coverage") or {}
    integrity_hold_reason = data_quality.get("integrity_hold_reason")
    
    health_score = metrics.get("health_score")
    valuation_score = metrics.get("valuation_score")
    valuation_status = metrics.get("valuation_status") or "Insufficient Data"
    applicability_profile = metrics.get("applicability_profile") or {}

    header_text = Paragraph(f"<b>Financial Statement Analysis Report: {company_name} ({symbol})</b><br/><font size=8.5 color='#2563EB'>Provider-Sourced Fundamentals with Separate Health and Valuation Screens</font><br/><font size=6.5 color='#64748B'>Report Generated: {report_generated_at}<br/>Market Data Captured: {market_data_as_of}<br/>Income Basis: {basis.get('income', 'unavailable')} through {basis.get('income_period_end', 'unavailable')}<br/>Balance Sheet: {basis.get('balance_sheet', 'unavailable')} at {basis.get('balance_sheet_period_end', 'unavailable')}</font>", title_style)

    if health_score is None:
        score_color = colors.HexColor("#64748B")
        score_display = "N/A"
    else:
        score_color = SUCCESS if health_score >= 80 else (WARNING if health_score >= 60 else DANGER)
        score_display = f"{health_score}/100"
    valuation_display = f"{valuation_score}/100" if valuation_score is not None else "N/A"
    score_box_html = (
        f"<font size=16 color='{score_color.hexval()}'><b>{score_display}</b></font>"
        "<br/><font size=6.5 color='#64748B'>Financial Health</font>"
        f"<br/><font size=8 color='#0F172A'><b>{valuation_display}</b></font>"
        f"<br/><font size=5.8 color='#64748B'>Valuation · {valuation_status}</font>"
    )
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

    # Section 1: Provider-sourced financial facts
    elements.append(Paragraph(f"1. Source Financial Statements & Balance Sheet Facts ({symbol})", section_heading))
    raw_fin = metrics.get("raw_financials", {})

    def format_money(val, currency=statement_currency):
        if val is None: return "N/A"
        prefix = f"{currency} " if currency else ""
        return f"{prefix}{val / 1e9:,.3f} Billion" if abs(val) >= 1e9 else f"{prefix}{val / 1e6:,.2f} Million"

    raw_table_data = [
        [
            Paragraph("<b>Financial Metric</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Analysis-Basis Value</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
            Paragraph("<b>Source Statement Line</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
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

    if sec_filing.get("status") == "verified":
        elements.append(Paragraph(
            f"<b>SEC filing recency check:</b> {sec_filing.get('form', 'filing')} filed {sec_filing.get('filed_date', 'date unavailable')} for report period {sec_filing.get('report_period', 'period unavailable')} (CIK {sec_filing.get('cik', 'unavailable')}). This verifies filing recency, not every standardized provider line item.",
            body_style,
        ))
        elements.append(Spacer(1, 4))

    if sec_fact_validation.get("status") == "matched":
        elements.append(Paragraph(
            f"<b>SEC numeric cross-check:</b> {sec_fact_validation.get('matched', 0)} of {sec_fact_validation.get('checked', 0)} comparable latest-quarter core facts matched SEC Company Facts within the stated tolerance.",
            body_style,
        ))
        elements.append(Spacer(1, 4))
    elif sec_fact_validation.get("status") == "mismatch":
        mismatch_names = ", ".join(item.get("metric", "unknown") for item in sec_fact_validation.get("mismatches", []))
        elements.append(Paragraph(
            f"<b>SEC numeric cross-check warning:</b> Comparable facts did not match for {mismatch_names or 'one or more core metrics'}. Review the filing before relying on calculated results.",
            body_style,
        ))
        elements.append(Spacer(1, 4))

    if calculation_coverage.get("core_input_count"):
        elements.append(Paragraph(
            f"<b>Calculation input coverage:</b> {calculation_coverage.get('available_core_input_count', 0)} of {calculation_coverage.get('core_input_count')} core inputs were available. Missing values were not estimated.",
            body_style,
        ))
        elements.append(Spacer(1, 4))

    if integrity_hold_reason:
        elements.append(Paragraph(f"<b>Score hold:</b> {integrity_hold_reason}", body_style))
        elements.append(Spacer(1, 4))

    # Section 2: Connected health, valuation and contextual diagnostics
    elements.append(Paragraph("2. Connected Financial-Health, Valuation & Context Diagnostics", section_heading))
    if applicability_profile:
        elements.append(Paragraph(
            f"<b>Applicable company model:</b> {applicability_profile.get('label', 'Unavailable')}. "
            f"{applicability_profile.get('rationale', '')}",
            body_style,
        ))
        elements.append(Spacer(1, 4))
    score_coverage = metrics.get("score_coverage") or {}
    if score_coverage:
        score_range = score_coverage.get("score_range") or {}
        range_text = (
            f" Evidence range: {score_range.get('low')}–{score_range.get('high')}/100."
            if score_range.get("low") is not None and score_range.get("high") is not None else ""
        )
        elements.append(Paragraph(
            f"<b>Health-model coverage:</b> {score_coverage.get('applicable_ratio_count', 0)} of "
            f"{score_coverage.get('model_ratio_count', 0)} inputs; "
            f"{score_coverage.get('coverage_label', 'Low')} coverage "
            f"({float(score_coverage.get('coverage_percent') or 0):.0%}).{range_text}",
            body_style,
        ))
        elements.append(Spacer(1, 4))
    ratio_evals = metrics.get("ratio_evaluations", {})

    table_data = [
        [
            Paragraph("<b>Model / Category</b>", ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
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
        status_label = item.get("status_label") or status
        score_model = item.get("score_model", "context")
        pts = item.get("pts", 0.0)
        weight = item.get("weight", 0.10)
        w_pts = item.get("w_pts", 0.0)

        if val is not None:
            val_str = fmt.format(val) if fmt == "{:.1%}" else f"{val:.2f}"
        else:
            val_str = status

        if status == "Healthy":
            status_cell = Paragraph(f"<font color='{SUCCESS.hexval()}'><b>{status_label}</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "Caution":
            status_cell = Paragraph(f"<font color='{WARNING.hexval()}'><b>{status_label}</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "Warning":
            status_cell = Paragraph(f"<font color='{DANGER.hexval()}'><b>{status_label}</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "N/M":
            status_cell = Paragraph("<font color='#D97706'><b>N/M</b></font>", ParagraphStyle('TD', fontSize=7))
        elif status == "Context":
            status_cell = Paragraph("<font color='#2563EB'><b>Context</b></font>", ParagraphStyle('TD', fontSize=7))
        else:
            status_cell = Paragraph(f"<font color='#64748B'><b>{status_label}</b></font>", ParagraphStyle('TD', fontSize=7))

        model_label = {
            "financial_health": "Health",
            "valuation": "Valuation",
            "context": "Context",
        }.get(score_model, "Context")

        table_data.append([
            Paragraph(f"<b>{model_label}</b><br/>{cat}", ParagraphStyle('TD', fontSize=7)),
            Paragraph(name, ParagraphStyle('TD', fontSize=7)),
            Paragraph(val_str, ParagraphStyle('TD', fontSize=7, fontName='Helvetica-Bold')),
            Paragraph(target, ParagraphStyle('TD', fontSize=6)),
            status_cell,
            Paragraph(f"{pts:.1f}", ParagraphStyle('TD', fontSize=7)),
            Paragraph(f"{weight*100:.1f}%" if score_model in {"financial_health", "valuation"} else "—", ParagraphStyle('TD', fontSize=7)),
            Paragraph(f"{w_pts:.1f}" if score_model in {"financial_health", "valuation"} else "—", ParagraphStyle('TD', fontSize=7, fontName='Helvetica-Bold'))
        ])

    ratio_table = Table(table_data, colWidths=[66, 129, 45, 145, 55, 30, 40, 30], repeatRows=1)
    ratio_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    elements.append(ratio_table)
    elements.append(Spacer(1, 6))

    # Section 3: Advanced diagnostics and supporting context
    elements.append(Paragraph("3. Advanced Financial Diagnostics & Supporting Context", section_heading))
    advanced = metrics.get("advanced_metrics") or {}
    advanced_definitions = [
        ("roic", "Return on invested capital", "percent", "NOPAT / average invested capital"),
        ("effective_tax_rate", "Effective tax rate", "percent", "Tax provision / pretax income"),
        ("accrual_ratio", "Accrual ratio", "percent", "(Net income - operating cash flow) / average assets"),
        ("operating_cash_flow_margin", "Operating cash flow margin", "percent", "Operating cash flow / revenue"),
        ("capex_to_revenue", "Capital spending / revenue", "percent", "Absolute capital expenditure / revenue"),
        ("dso", "Days sales outstanding", "days", "365 × average receivables / revenue"),
        ("dio", "Days inventory outstanding", "days", "365 × average inventory / cost of revenue"),
        ("dpo", "Days payable outstanding", "days", "365 × average payables / cost of revenue"),
        ("cash_conversion_cycle", "Cash conversion cycle", "days", "DSO + DIO - DPO"),
        ("stock_comp_to_revenue", "Stock compensation / revenue", "percent", "Stock-based compensation / revenue"),
        ("stock_comp_to_fcf", "Stock compensation / FCF", "percent", "Stock-based compensation / free cash flow"),
        ("shareholder_yield", "Shareholder yield", "percent", "(Dividends + net buybacks) / market capitalization"),
        ("price_to_sales", "Price / sales", "multiple", "Market capitalization / revenue"),
        ("price_to_book", "Price / book", "multiple", "Market capitalization / equity"),
        ("ev_to_sales", "Enterprise value / sales", "multiple", "Enterprise value / revenue"),
        ("earnings_yield", "Earnings yield", "percent", "Net income / market capitalization"),
        ("annual_eps_growth", "Annual diluted EPS growth", "percent", "Latest annual EPS / prior annual EPS - 1"),
        ("annual_fcf_growth", "Annual free cash flow growth", "percent", "Latest annual FCF / prior annual FCF - 1"),
    ]

    def format_advanced(value, kind):
        if value is None:
            return "N/A"
        if kind == "percent":
            return f"{value:.1%}"
        if kind == "multiple":
            return f"{value:.2f}x"
        if kind == "days":
            return f"{value:.1f} days"
        return f"{value:.2f}"

    advanced_rows = [[
        Paragraph("<b>Metric</b>", ParagraphStyle('ATH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
        Paragraph("<b>Result</b>", ParagraphStyle('ATH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
        Paragraph("<b>Formula</b>", ParagraphStyle('ATH', fontName='Helvetica-Bold', fontSize=7, textColor=PRIMARY)),
    ]]
    for key, name, kind, formula in advanced_definitions:
        advanced_rows.append([
            Paragraph(name, ParagraphStyle('ATD', fontSize=7)),
            Paragraph(format_advanced(advanced.get(key), kind), ParagraphStyle('ATD', fontSize=7, fontName='Helvetica-Bold')),
            Paragraph(formula, ParagraphStyle('ATD', fontSize=6.5)),
        ])
    advanced_table = Table(advanced_rows, colWidths=[145, 75, 320], repeatRows=1)
    advanced_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), BG_LIGHT),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    elements.append(advanced_table)
    elements.append(Paragraph(
        "These measures are calculated only from exact reported inputs. Some feed the health or valuation screen as identified in Section 2; the remainder are context only. N/A means at least one required input was unavailable; no value was estimated.",
        body_style,
    ))
    elements.append(Spacer(1, 6))

    # Section 4: Market Valuation & EV/EBITDA
    elements.append(Paragraph("4. Market Valuation & Enterprise Value Breakdown", section_heading))

    price_val = ev_b.get("share_price")
    price_str = f"{market_currency} {price_val:.2f}" if price_val else "N/A"
    
    eve_val = ev_b.get("ev_ebitda_std")
    eve_str = f"{eve_val:.2f}x" if eve_val else "N/A"

    ev_box_data = [
        [
            Paragraph(f"<b>Market Capitalization:</b> {format_money(ev_b.get('market_cap'), market_currency)} (Share Price {price_str})", body_style),
            Paragraph(f"<b>Operating Income (EBIT):</b> {format_money(ev_b.get('operating_income'))}", body_style)
        ],
        [
            Paragraph(f"<b>(+) Total Debt Obligations:</b> {format_money(ev_b.get('total_debt'))}", body_style),
            Paragraph(f"<b>(+) Depreciation & Amortization:</b> {format_money(ev_b.get('depreciation_amortization'))}", body_style)
        ],
        [
            Paragraph(f"<b>(-) Cash & Short-Term Investments:</b> {format_money(ev_b.get('cash_and_short_term'))}", body_style),
            Paragraph(f"<b>(=) EBITDA:</b> <b>{format_money(ev_b.get('ebitda'))}</b> ({ev_b.get('ebitda_method') or 'method unavailable'})", body_style)
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

    # Section 5: Deterministic contextual analysis
    elements.append(Paragraph("5. Rules-Based Briefing & Contextual Financial Drivers", section_heading))
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
    footer_p = Paragraph(f"<font color='#94A3B8'>StatementIQ Financial Analysis Report for {company_name} ({symbol}). Financial Health: {score_display}. Separate Valuation Screen: {valuation_display}. Missing source values are shown as N/A. These transparent rules-based screens are not investment advice, a credit opinion, or a substitute for reviewing complete filings and industry context.</font>", ParagraphStyle('Foot', fontName='Helvetica-Oblique', fontSize=6.5, align=TA_CENTER))
    elements.append(footer_p)

    doc.build(elements)
    buffer.seek(0)
    return buffer
