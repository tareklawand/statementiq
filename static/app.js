// Global State
let currentSymbol = "AAPL";
let currentData = null;
let activeStatementType = "income_statement";

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    fetchPresets();
    loadTickerData("AAPL");
    setupEventListeners();
});

// Event Listeners Setup
function setupEventListeners() {
    // Search Button Click
    document.getElementById("searchBtn").addEventListener("click", () => {
        const inputVal = document.getElementById("tickerSearchInput").value.trim();
        if (inputVal) {
            loadTickerData(inputVal);
        }
    });

    // Enter Key Search Input
    document.getElementById("tickerSearchInput").addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            const inputVal = e.target.value.trim();
            if (inputVal) {
                loadTickerData(inputVal);
            }
        }
    });

    // Tabs Switch
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            
            const targetTab = e.currentTarget.getAttribute("data-tab");
            e.currentTarget.classList.add("active");
            document.getElementById(targetTab).classList.add("active");

            // Trigger Plotly relayout to fit container if needed
            window.dispatchEvent(new Event('resize'));
        });
    });

    // Financial Statement Switch Buttons
    document.querySelectorAll(".stmt-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".stmt-btn").forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");
            activeStatementType = e.currentTarget.getAttribute("data-stmt");
            renderFinancialStatementTable();
        });
    });

    // Financial Statement Search Filter
    document.getElementById("statementSearchInput").addEventListener("input", () => {
        renderFinancialStatementTable();
    });

    // PDF Download Button
    document.getElementById("downloadPdfBtn").addEventListener("click", handlePdfDownload);
}

// Fetch Preset Bluechips
async function fetchPresets() {
    try {
        const res = await fetch("/api/presets");
        const data = await res.json();
        const ribbon = document.getElementById("tickerRibbon");
        
        if (data.presets) {
            Object.entries(data.presets).forEach(([label, symbol]) => {
                const pill = document.createElement("div");
                pill.className = `ticker-pill ${symbol === currentSymbol ? 'active' : ''}`;
                pill.innerText = symbol;
                pill.addEventListener("click", () => loadTickerData(symbol));
                ribbon.appendChild(pill);
            });
        }
    } catch (err) {
        console.error("Failed to fetch presets:", err);
    }
}

// Load Stock Data from API
async function loadTickerData(symbol) {
    const searchBtn = document.getElementById("searchBtn");
    searchBtn.disabled = true;
    searchBtn.innerText = "LOADING...";

    const apiKey = document.getElementById("geminiApiKey").value.trim();
    let url = `/api/analyze?ticker=${encodeURIComponent(symbol)}`;
    if (apiKey) {
        url += `&api_key=${encodeURIComponent(apiKey)}`;
    }

    try {
        const res = await fetch(url);
        if (!res.ok) {
            const errData = await res.json();
            alert(errData.detail || `Failed to fetch data for ${symbol}`);
            return;
        }

        currentData = await res.json();
        currentSymbol = currentData.symbol;

        // Update Pill Active States
        document.querySelectorAll(".ticker-pill").forEach(pill => {
            if (pill.innerText === currentSymbol) {
                pill.classList.add("active");
            } else {
                pill.classList.remove("active");
            }
        });

        // Render UI Sections
        renderHeroBanner();
        renderKPIs();
        renderAIBriefing();
        renderStrengthsWeaknesses();
        renderCharts();
        renderRatioCards();
        renderFinancialStatementTable();

    } catch (err) {
        console.error("Error loading ticker data:", err);
        alert(`Network error fetching data for ${symbol}`);
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerText = "ANALYZE";
        lucide.createIcons();
    }
}

// Render Hero Banner Header
function renderHeroBanner() {
    document.getElementById("heroCompanyName").innerText = currentData.company_name;
    document.getElementById("heroSymbol").innerText = currentData.symbol;
    document.getElementById("heroSector").innerText = currentData.info.sector || "N/A";
    document.getElementById("heroIndustry").innerText = currentData.info.industry || "N/A";
    document.getElementById("heroCurrency").innerText = currentData.info.currency || "USD";
}

// Render KPI Cards
function renderKPIs() {
    const info = currentData.info;
    
    document.getElementById("kpiPrice").innerText = info.price ? `$${info.price.toFixed(2)}` : "N/A";
    document.getElementById("kpiMarketCap").innerText = info.market_cap ? `$${(info.market_cap / 1e9).toFixed(2)}B` : "N/A";
    document.getElementById("kpiPE").innerText = info.pe_ratio ? `${info.pe_ratio.toFixed(2)}x` : "N/A";
    document.getElementById("kpiTargetPrice").innerText = info.target_price ? `$${info.target_price.toFixed(2)}` : "N/A";
}

// Render AI Briefing & Health Score Gauge
function renderAIBriefing() {
    const ai = currentData.ai_insights;
    const metrics = currentData.metrics;

    document.getElementById("aiExecutiveSummary").innerText = ai.executive_summary || "N/A";
    document.getElementById("aiScoreExplanation").innerText = ai.score_explanation || "N/A";
    
    const statusText = document.getElementById("healthStatusText");
    statusText.innerText = metrics.health_status.toUpperCase();
    
    if (metrics.health_score >= 80) {
        statusText.style.color = "#10B981";
    } else if (metrics.health_score >= 60) {
        statusText.style.color = "#F59E0B";
    } else {
        statusText.style.color = "#EF4444";
    }

    renderGaugeChart(metrics.health_score);
}

// Render Strengths & Weaknesses
function renderStrengthsWeaknesses() {
    const ai = currentData.ai_insights;

    const strContainer = document.getElementById("strengthsContainer");
    strContainer.innerHTML = "";
    (ai.top_strengths || []).forEach(s => {
        const item = document.createElement("div");
        item.className = "strength-item-card";
        item.innerHTML = `<b>•</b> ${s}`;
        strContainer.appendChild(item);
    });

    const weakContainer = document.getElementById("weaknessesContainer");
    weakContainer.innerHTML = "";
    (ai.top_weaknesses || []).forEach(w => {
        const item = document.createElement("div");
        item.className = "weakness-item-card";
        item.innerHTML = `<b>•</b> ${w}`;
        weakContainer.appendChild(item);
    });
}

// Render Gauge Chart
function renderGaugeChart(score) {
    let accentColor = "#10B981";
    if (score < 60) accentColor = "#EF4444";
    else if (score < 80) accentColor = "#F59E0B";

    const gaugeData = [{
        type: "indicator",
        mode: "gauge+number",
        value: score,
        domain: { x: [0, 1], y: [0, 1] },
        number: { suffix: " / 100", font: { size: 36, color: "#F8FAFC", family: "Outfit, sans-serif" } },
        gauge: {
            axis: { range: [0, 100], tickwidth: 1, tickcolor: "#94A3B8", dtick: 20 },
            bar: { color: accentColor, thickness: 0.85 },
            bgcolor: "#090D15",
            borderwidth: 1,
            bordercolor: "#1E293B",
            steps: [
                { range: [0, 60], color: "rgba(239, 68, 68, 0.12)" },
                { range: [60, 80], color: "rgba(245, 158, 11, 0.12)" },
                { range: [80, 100], color: "rgba(16, 185, 129, 0.12)" }
            ]
        }
    }];

    const layout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: { l: 20, r: 20, t: 20, b: 10 },
        height: 200
    };

    Plotly.newPlot("healthGaugeChart", gaugeData, layout, { responsive: true, displayModeBar: false });
}

// Render Plotly Financial Performance Charts
function renderCharts() {
    const perf = currentData.charts.financial_performance;
    const cashDebt = currentData.charts.cash_vs_debt;

    // 1. Revenue & Net Income Chart
    const revTrace = {
        x: perf.years,
        y: perf.revenue,
        name: "Revenue ($B)",
        type: "bar",
        marker: { color: "rgba(59, 130, 246, 0.85)", line: { color: "#3B82F6", width: 1.5 } }
    };

    const niTrace = {
        x: perf.years,
        y: perf.net_income,
        name: "Net Income ($B)",
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#10B981", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#10B981" }
    };

    const layout1 = {
        title: { text: "<b>Revenue & Net Income Trend</b> ($ Billions)", font: { color: "#F8FAFC", family: "Outfit", size: 14 } },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#94A3B8" },
        xaxis: { showgrid: false, linecolor: "#1E293B" },
        yaxis: { showgrid: true, gridcolor: "rgba(255,255,255,0.05)" },
        legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
        margin: { l: 40, r: 20, t: 40, b: 35 },
        height: 330
    };

    Plotly.newPlot("chartRevenueNetIncome", [revTrace, niTrace], layout1, { responsive: true, displayModeBar: false });

    // 2. Cash vs Debt Chart
    const cashTrace = {
        x: cashDebt.years,
        y: cashDebt.cash,
        name: "Cash & Equivalents",
        type: "bar",
        marker: { color: "rgba(16, 185, 129, 0.85)", line: { color: "#10B981", width: 1.5 } }
    };

    const debtTrace = {
        x: cashDebt.years,
        y: cashDebt.debt,
        name: "Total Debt",
        type: "bar",
        marker: { color: "rgba(239, 68, 68, 0.85)", line: { color: "#EF4444", width: 1.5 } }
    };

    const layout2 = {
        title: { text: "<b>Cash vs Total Debt Comparison</b> ($ Billions)", font: { color: "#F8FAFC", family: "Outfit", size: 14 } },
        barmode: "group",
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#94A3B8" },
        xaxis: { showgrid: false, linecolor: "#1E293B" },
        yaxis: { showgrid: true, gridcolor: "rgba(255,255,255,0.05)" },
        legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
        margin: { l: 40, r: 20, t: 40, b: 35 },
        height: 330
    };

    Plotly.newPlot("chartCashVsDebt", [cashTrace, debtTrace], layout2, { responsive: true, displayModeBar: false });

    // 3. Margin Trend Chart
    const gmTrace = {
        x: perf.years,
        y: perf.gross_margin,
        name: "Gross Margin (%)",
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#8B5CF6", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#8B5CF6" }
    };

    const nmTrace = {
        x: perf.years,
        y: perf.net_margin,
        name: "Net Profit Margin (%)",
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#F59E0B", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#F59E0B" }
    };

    const layout3 = {
        title: { text: "<b>Margin Expansion & Profitability Dynamics</b> (%)", font: { color: "#F8FAFC", family: "Outfit", size: 14 } },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: "#94A3B8" },
        xaxis: { showgrid: false, linecolor: "#1E293B" },
        yaxis: { showgrid: true, gridcolor: "rgba(255,255,255,0.05)" },
        legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
        margin: { l: 40, r: 20, t: 40, b: 35 },
        height: 330
    };

    Plotly.newPlot("chartMargins", [gmTrace, nmTrace], layout3, { responsive: true, displayModeBar: false });
}

// Render Ratio Cards Grouped by Category
function renderRatioCards() {
    const ratioEvals = currentData.metrics.ratio_evaluations;
    const container = document.getElementById("ratiosCategoriesContainer");
    container.innerHTML = "";

    // Group by category
    const categories = {};
    Object.values(ratioEvals).forEach(item => {
        const cat = item.category || "General";
        if (!categories[cat]) categories[cat] = [];
        categories[cat].push(item);
    });

    Object.entries(categories).forEach(([catName, items]) => {
        const catHeader = document.createElement("div");
        catHeader.className = "category-title";
        catHeader.innerText = catName.toUpperCase();
        container.appendChild(catHeader);

        const grid = document.createElement("div");
        grid.className = "ratio-cards-grid";

        items.forEach(item => {
            const card = document.createElement("div");
            card.className = "ratio-card";

            let statusClass = "healthy";
            let fillClass = "green";
            let pct = 85;

            if (item.status === "Caution") {
                statusClass = "caution";
                fillClass = "amber";
                pct = 55;
            } else if (item.status === "Warning") {
                statusClass = "warning";
                fillClass = "red";
                pct = 30;
            }

            let valStr = "N/A";
            if (item.value !== null && item.value !== undefined) {
                if (item.format === "{:.1%}") {
                    valStr = `${(item.value * 100).toFixed(1)}%`;
                } else {
                    valStr = item.value.toFixed(2);
                }
            }

            card.innerHTML = `
                <div class="ratio-card-header">
                    <span class="ratio-cat-tag">${catName}</span>
                    <span class="status-pill ${statusClass}">● ${item.status.toUpperCase()} (Target ${item.target})</span>
                </div>
                <div class="ratio-name">${item.name}</div>
                <div class="ratio-val-large">${valStr}</div>
                <div class="progress-track">
                    <div class="progress-fill ${fillClass}" style="width: ${pct}%;"></div>
                </div>
            `;

            grid.appendChild(card);
        });

        container.appendChild(grid);
    });
}

// Render Financial Statements Data Table
function renderFinancialStatementTable() {
    const stmtData = currentData.statements[activeStatementType];
    const container = document.getElementById("statementTableContainer");
    
    if (!stmtData || !stmtData.rows || stmtData.rows.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:40px; color:#94A3B8;">No statement data available for ${currentSymbol}.</div>`;
        return;
    }

    const filterVal = document.getElementById("statementSearchInput").value.trim().toLowerCase();

    let tableHtml = `<table class="financial-table"><thead><tr><th>Metric Row</th>`;
    stmtData.columns.forEach(col => {
        tableHtml += `<th>${col}</th>`;
    });
    tableHtml += `</tr></thead><tbody>`;

    stmtData.rows.forEach(row => {
        if (filterVal && !row.metric.toLowerCase().includes(filterVal)) {
            return;
        }

        tableHtml += `<tr><td>${row.metric}</td>`;
        row.values.forEach(v => {
            if (v === null || v === undefined) {
                tableHtml += `<td>-</td>`;
            } else if (typeof v === "number") {
                const valClass = v < 0 ? "val-negative" : "val-positive";
                const fmtVal = Math.abs(v) >= 1e6 ? `$${(v / 1e6).toLocaleString(undefined, {maximumFractionDigits: 0})}M` : `$${v.toLocaleString()}`;
                tableHtml += `<td class="${valClass}">${fmtVal}</td>`;
            } else {
                tableHtml += `<td>${v}</td>`;
            }
        });
        tableHtml += `</tr>`;
    });

    tableHtml += `</tbody></table>`;
    container.innerHTML = tableHtml;
}

// Handle PDF Export Stream
async function handlePdfDownload() {
    if (!currentData) return;

    const btn = document.getElementById("downloadPdfBtn");
    btn.disabled = true;
    btn.innerText = "COMPILING PDF...";

    try {
        const payload = {
            symbol: currentData.symbol,
            company_name: currentData.company_name,
            metrics: currentData.metrics,
            ai_insights: currentData.ai_insights
        };

        const res = await fetch("/api/download-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            alert("Failed to compile PDF report.");
            return;
        }

        const blob = await res.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `${currentData.symbol}_Financial_Audit_Report.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();

    } catch (err) {
        console.error("PDF Download error:", err);
        alert("Error downloading PDF report.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="file-down"></i> EXPORT PDF AUDIT REPORT`;
        lucide.createIcons();
    }
}
