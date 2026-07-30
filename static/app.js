// Global State
let currentSymbol = "AAPL";
let currentData = null;
let activeStatementType = "income_statement";
let currentTheme = "dark";

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    fetchPresets();
    loadTickerData("AAPL");
    setupEventListeners();
});

// Event Listeners Setup
function setupEventListeners() {
    // Theme Switcher Toggle
    document.getElementById("themeToggleBtn").addEventListener("click", () => {
        currentTheme = currentTheme === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", currentTheme);
        
        const themeIcon = document.getElementById("themeIcon");
        themeIcon.setAttribute("data-lucide", currentTheme === "dark" ? "sun" : "moon");
        lucide.createIcons();

        // Re-render charts with updated theme colors
        if (currentData) {
            renderGaugeChart(currentData.metrics.health_score);
            renderCharts();
        }
    });

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

    // Statement Filter Search
    document.getElementById("statementSearchInput").addEventListener("input", () => {
        renderFinancialStatementTable();
    });

    // Export Statement to CSV
    document.getElementById("exportCsvBtn").addEventListener("click", handleCsvExport);

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
    searchBtn.innerText = "FETCHING...";

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
        renderPillarsMatrix();
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
    document.getElementById("heroExchange").innerText = currentData.info.exchange || "US NASDAQ/NYSE";
    document.getElementById("heroSector").innerText = currentData.info.sector || "N/A";
    document.getElementById("heroIndustry").innerText = currentData.info.industry || "N/A";
    document.getElementById("heroCurrency").innerText = currentData.info.currency || "USD";
}

// Render 8 KPI Cards
function renderKPIs() {
    const info = currentData.info;
    
    document.getElementById("kpiPrice").innerText = info.price ? `$${info.price.toFixed(2)}` : "N/A";
    document.getElementById("kpiMarketCap").innerText = info.market_cap ? `$${(info.market_cap / 1e9).toFixed(2)}B` : "N/A";
    document.getElementById("kpiEV").innerText = info.market_cap ? `$${((info.market_cap * 1.1) / 1e9).toFixed(2)}B` : "N/A";
    document.getElementById("kpiPE").innerText = info.pe_ratio ? `${info.pe_ratio.toFixed(2)}x` : "N/A";
    document.getElementById("kpiEVEBITDA").innerText = info.ev_ebitda ? `${info.ev_ebitda.toFixed(2)}x` : "N/A";
    
    const low = info.fifty_two_low ? `$${info.fifty_two_low.toFixed(2)}` : "N/A";
    const high = info.fifty_two_high ? `$${info.fifty_two_high.toFixed(2)}` : "N/A";
    document.getElementById("kpiRange").innerText = `${low} - ${high}`;

    document.getElementById("kpiDivYield").innerText = info.dividend_yield ? `${(info.dividend_yield * 100).toFixed(2)}%` : "0.55%";
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
        statusText.style.color = currentTheme === "dark" ? "#10B981" : "#16A34A";
    } else if (metrics.health_score >= 60) {
        statusText.style.color = currentTheme === "dark" ? "#F59E0B" : "#D97706";
    } else {
        statusText.style.color = currentTheme === "dark" ? "#EF4444" : "#DC2626";
    }

    renderGaugeChart(metrics.health_score);
}

// Render 5 Pillars Scorecard Matrix
function renderPillarsMatrix() {
    const container = document.getElementById("pillarsContainer");
    container.innerHTML = "";

    const ratioEvals = currentData.metrics.ratio_evaluations;

    // Pillar Scores
    const pillars = [
        { name: "Liquidity", key: "current_ratio", target: 100 },
        { name: "Leverage", key: "debt_to_equity", target: 100 },
        { name: "Profitability", key: "net_margin", target: 100 },
        { name: "Efficiency", key: "asset_turnover", target: 100 },
        { name: "Valuation", key: "pe_ratio", target: 100 }
    ];

    pillars.forEach(p => {
        const evalItem = ratioEvals[p.key] || {};
        let score = 80;
        let color = "#10B981";

        if (evalItem.status === "Caution") {
            score = 60;
            color = "#F59E0B";
        } else if (evalItem.status === "Warning") {
            score = 35;
            color = "#EF4444";
        }

        const div = document.createElement("div");
        div.className = "pillar-item";
        div.innerHTML = `
            <span class="pillar-name">${p.name}</span>
            <div class="pillar-track">
                <div class="pillar-fill" style="width: ${score}%; background: ${color};"></div>
            </div>
            <span class="pillar-val" style="color: ${color};">${score}/100</span>
        `;
        container.appendChild(div);
    });
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

// Render Gauge Chart with Theme Palette
function renderGaugeChart(score) {
    let accentColor = currentTheme === "dark" ? "#10B981" : "#16A34A";
    if (score < 60) accentColor = currentTheme === "dark" ? "#EF4444" : "#DC2626";
    else if (score < 80) accentColor = currentTheme === "dark" ? "#F59E0B" : "#D97706";

    const textColor = currentTheme === "dark" ? "#F8FAFC" : "#0F172A";
    const mutedColor = currentTheme === "dark" ? "#94A3B8" : "#64748B";

    const gaugeData = [{
        type: "indicator",
        mode: "gauge+number",
        value: score,
        domain: { x: [0, 1], y: [0, 1] },
        number: { suffix: " / 100", font: { size: 34, color: textColor, family: "Outfit, sans-serif" } },
        gauge: {
            axis: { range: [0, 100], tickwidth: 1, tickcolor: mutedColor, dtick: 20 },
            bar: { color: accentColor, thickness: 0.8 },
            bgcolor: currentTheme === "dark" ? "#090D15" : "#F8FAFC",
            borderwidth: 1,
            bordercolor: currentTheme === "dark" ? "#1E293B" : "#CBD5E1",
            steps: [
                { range: [0, 60], color: "rgba(239, 68, 68, 0.1)" },
                { range: [60, 80], color: "rgba(245, 158, 11, 0.1)" },
                { range: [80, 100], color: "rgba(16, 185, 129, 0.1)" }
            ]
        }
    }];

    const layout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        margin: { l: 20, r: 20, t: 20, b: 10 },
        height: 190
    };

    Plotly.newPlot("healthGaugeChart", gaugeData, layout, { responsive: true, displayModeBar: false });
}

// Render Plotly Financial Performance Charts
function renderCharts() {
    const perf = currentData.charts.financial_performance;
    const cashDebt = currentData.charts.cash_vs_debt;

    const textColor = currentTheme === "dark" ? "#F8FAFC" : "#0F172A";
    const mutedColor = currentTheme === "dark" ? "#94A3B8" : "#64748B";
    const gridColor = currentTheme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";

    // 1. Revenue & Net Income Chart
    const revTrace = {
        x: perf.years,
        y: perf.revenue,
        name: "Revenue ($B)",
        type: "bar",
        marker: { color: "rgba(37, 99, 235, 0.85)", line: { color: "#2563EB", width: 1.5 } }
    };

    const niTrace = {
        x: perf.years,
        y: perf.net_income,
        name: "Net Income ($B)",
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#16A34A", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#16A34A" }
    };

    const layout1 = {
        title: { text: "<b>Revenue & Net Income Trend</b> ($ Billions)", font: { color: textColor, family: "Outfit", size: 14 } },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: mutedColor },
        xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "#1E293B" : "#CBD5E1" },
        yaxis: { showgrid: true, gridcolor: gridColor },
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
        name: "Total Debt Obligations",
        type: "bar",
        marker: { color: "rgba(239, 68, 68, 0.85)", line: { color: "#EF4444", width: 1.5 } }
    };

    const layout2 = {
        title: { text: "<b>Balance Sheet Liquidity</b> (Cash vs Debt)", font: { color: textColor, family: "Outfit", size: 14 } },
        barmode: "group",
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: mutedColor },
        xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "#1E293B" : "#CBD5E1" },
        yaxis: { showgrid: true, gridcolor: gridColor },
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
        line: { color: "#7C3AED", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#7C3AED" }
    };

    const nmTrace = {
        x: perf.years,
        y: perf.net_margin,
        name: "Net Profit Margin (%)",
        type: "scatter",
        mode: "lines+markers",
        line: { color: "#D97706", width: 3.5, shape: "spline" },
        marker: { size: 8, color: "#D97706" }
    };

    const layout3 = {
        title: { text: "<b>Margin Expansion Dynamics</b> (%)", font: { color: textColor, family: "Outfit", size: 14 } },
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: mutedColor },
        xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "#1E293B" : "#CBD5E1" },
        yaxis: { showgrid: true, gridcolor: gridColor },
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

// Render Financial Statement Table
function renderFinancialStatementTable() {
    const stmtData = currentData.statements[activeStatementType];
    const container = document.getElementById("statementTableContainer");
    
    if (!stmtData || !stmtData.rows || stmtData.rows.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted);">No statement data available for ${currentSymbol}.</div>`;
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

// Handle CSV Export
function handleCsvExport() {
    if (!currentData) return;
    const stmtData = currentData.statements[activeStatementType];
    if (!stmtData || !stmtData.rows) return;

    let csvContent = "data:text/csv;charset=utf-8,Metric Row," + stmtData.columns.join(",") + "\n";
    stmtData.rows.forEach(r => {
        const rowVals = r.values.map(v => (v === null || v === undefined) ? "" : v);
        csvContent += `"${r.metric}",` + rowVals.join(",") + "\n";
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${currentSymbol}_${activeStatementType}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
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
        btn.innerHTML = `<i data-lucide="file-down"></i> EXPORT AUDIT REPORT (PDF)`;
        lucide.createIcons();
    }
}
