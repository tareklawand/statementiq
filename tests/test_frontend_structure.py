from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


def _tab_markup(html: str, tab_id: str, next_tab_id: Optional[str] = None) -> str:
    start = html.index(f'id="{tab_id}"')
    end = html.index(f'id="{next_tab_id}"', start) if next_tab_id else len(html)
    return html[start:end]


def test_statement_analysis_and_filing_review_live_with_reported_statements():
    html = (ROOT / "static" / "index.html").read_text()
    ratio_tab = _tab_markup(html, "tab2", "tab3")
    statement_tab = _tab_markup(html, "tab3")

    assert 'id="supportingAnalysisContainer"' in ratio_tab
    assert 'id="statementAnalysisContainer"' not in ratio_tab
    assert 'id="filingReviewContainer"' not in ratio_tab
    assert 'id="statementAnalysisContainer"' in statement_tab
    assert 'id="filingReviewContainer"' in statement_tab


def test_ratio_diagnostics_explain_health_valuation_and_context_metrics():
    script = (ROOT / "static" / "app.js").read_text()

    for category in ("Liquidity", "Leverage", "Profitability", "Efficiency", "Valuation"):
        assert category in script
    assert "Health score input" in script
    assert "Valuation score input" in script
    assert "Context only" in script
    assert "contributes no score points" in script
    assert "renderSupportingAnalysis" in script
