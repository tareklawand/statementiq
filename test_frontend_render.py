import urllib.request
import json

url = "http://localhost:8888/api/analyze?ticker=AAPL"
req = urllib.request.urlopen(url)
data = json.loads(req.read().decode('utf-8'))

print("CurrentData Top Level Keys:", list(data.keys()))
print("info:", data.get("info"))
print("metrics keys:", list(data["metrics"].keys()))
print("ai_insights keys:", list(data["ai_insights"].keys()))
print("charts keys:", list(data["charts"].keys()))
print("statements keys:", list(data["statements"].keys()))

# Check properties accessed in app.js
info = data["info"]
print("\nKPI Access Test:")
print("price:", info.get("price"))
print("market_cap:", info.get("market_cap"))
print("pe_ratio:", info.get("pe_ratio"))
print("ev_ebitda:", info.get("ev_ebitda"))

ai = data["ai_insights"]
print("\nAI Access Test:")
print("executive_summary:", ai.get("executive_summary"))
print("score_explanation:", ai.get("score_explanation"))
print("top_strengths:", ai.get("top_strengths"))
print("top_weaknesses:", ai.get("top_weaknesses"))

metrics = data["metrics"]
print("\nMetrics Access Test:")
print("health_score:", metrics.get("health_score"))
print("health_status:", metrics.get("health_status"))
print("ratio_evaluations count:", len(metrics.get("ratio_evaluations", {})))

charts = data["charts"]
print("\nCharts Access Test:")
print("financial_performance:", charts.get("financial_performance"))
print("cash_vs_debt:", charts.get("cash_vs_debt"))

statements = data["statements"]
print("\nStatements Access Test:")
print("income_statement rows count:", len(statements.get("income_statement", {}).get("rows", [])))
print("balance_sheet rows count:", len(statements.get("balance_sheet", {}).get("rows", [])))
print("cash_flow rows count:", len(statements.get("cash_flow", {}).get("rows", [])))
