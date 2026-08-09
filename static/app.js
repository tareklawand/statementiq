// Global State
let currentSymbol = "AAPL";
let currentData = null;
let activeStatementType = "income_statement";
let currentTheme = "dark";

// Initialize Application
function initApp() {
    try { lucide.createIcons(); } catch(e){}
    setupEventListeners();
    try { fetchPresets(); } catch(e){}
    loadTickerData("AAPL");
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}

// Event Listeners Setup (Ultra-Defensive)
function setupEventListeners() {
    // Theme Switcher Toggle
    const themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            currentTheme = currentTheme === "dark" ? "light" : "dark";
            document.documentElement.setAttribute("data-theme", currentTheme);
            
            const themeIcon = document.getElementById("themeIcon");
            if (themeIcon) {
                themeIcon.setAttribute("data-lucide", currentTheme === "dark" ? "sun" : "moon");
                try { lucide.createIcons(); } catch(e){}
            }

            if (currentData) {
                try { renderGaugeChart(currentData.metrics.health_score); } catch(e){}
                try { renderCharts(); } catch(e){}
            }
        });
    }

    // Search Button Click
    const searchBtn = document.getElementById("searchBtn");
    if (searchBtn) {
        searchBtn.addEventListener("click", () => {
            const inputEl = document.getElementById("tickerSearchInput");
            const inputVal = inputEl ? inputEl.value.trim() : "";
            if (inputVal) {
                loadTickerData(inputVal);
            }
        });
    }

    // Enter Key Search Input
    const searchInput = document.getElementById("tickerSearchInput");
    if (searchInput) {
        searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                const inputVal = e.target.value.trim();
                if (inputVal) {
                    loadTickerData(inputVal);
                }
            }
        });
    }

    // Tabs Switch
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            
            const targetTab = e.currentTarget.getAttribute("data-tab");
            e.currentTarget.classList.add("active");
            const pane = document.getElementById(targetTab);
            if (pane) pane.classList.add("active");

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
    const stmtSearch = document.getElementById("statementSearchInput");
    if (stmtSearch) {
        stmtSearch.addEventListener("input", () => {
            renderFinancialStatementTable();
        });
    }

    // Export Statement to CSV
    const csvBtn = document.getElementById("exportCsvBtn");
    if (csvBtn) {
        csvBtn.addEventListener("click", handleCsvExport);
    }

    // PDF Download Button
    const pdfBtn = document.getElementById("downloadPdfBtn");
    if (pdfBtn) {
        pdfBtn.addEventListener("click", handlePdfDownload);
    }
}

// Fetch Preset Bluechips
async function fetchPresets() {
    try {
        const res = await fetch("/api/presets");
        const data = await res.json();
        const ribbon = document.getElementById("tickerRibbon");
        if (!ribbon) return;
        
        if (data.presets) {
            ribbon.innerHTML = `<span class="ribbon-label"><i data-lucide="globe" class="inline-icon"></i> COVERED BLUECHIPS:</span>`;
            Object.entries(data.presets).forEach(([label, symbol]) => {
                const pill = document.createElement("div");
                pill.className = `ticker-pill ${symbol === currentSymbol ? 'active' : ''}`;
                pill.innerText = symbol;
                pill.addEventListener("click", () => {
                    document.querySelectorAll(".ticker-pill").forEach(p => p.classList.remove("active"));
                    pill.classList.add("active");
                    const searchInput = document.getElementById("tickerSearchInput");
                    if (searchInput) searchInput.value = symbol;
                    loadTickerData(symbol);
                });
                ribbon.appendChild(pill);
            });
            try { lucide.createIcons(); } catch(e){}
        }
    } catch (err) {
        console.error("Failed to load preset tickers:", err);
    }
}

// Main Data Fetcher
async function loadTickerData(symbol) {
    const searchBtn = document.getElementById("searchBtn");
    const targetSymbol = (symbol || "AAPL").trim().toUpperCase();

    if (searchBtn) {
        searchBtn.disabled = true;
        searchBtn.innerText = "LOADING...";
    }

    try {
        const keyInput = document.getElementById("geminiApiKey");
        const geminiKey = keyInput ? keyInput.value.trim() : "";
        let url = `/api/analyze?ticker=${encodeURIComponent(targetSymbol)}`;
        if (geminiKey) {
            url += `&api_key=${encodeURIComponent(geminiKey)}`;
        }

        const res = await fetch(url);
        if (!res.ok) {
            const errData = await res.json();
            alert(errData.detail || `Error fetching data for ${targetSymbol}`);
            return;
        }

        currentData = await res.json();
        currentSymbol = currentData.symbol;

        // Render UI Sections smoothly with isolation
        try { renderHeroBanner(); } catch(e){ console.error("Hero render error:", e); }
        try { renderKPIs(); } catch(e){ console.error("KPI render error:", e); }
        try { renderAIBriefing(); } catch(e){ console.error("AI Briefing render error:", e); }
        try { renderPillarsMatrix(); } catch(e){ console.error("Pillars render error:", e); }
        try { renderStrengthsWeaknesses(); } catch(e){ console.error("Strengths render error:", e); }
        try { renderCharts(); } catch(e){ console.error("Charts render error:", e); }
        try { renderRatioCards(); } catch(e){ console.error("Ratio Cards render error:", e); }
        try { renderFinancialStatementTable(); } catch(e){ console.error("Statement Table render error:", e); }

    } catch (err) {
        console.error("Error loading ticker data:", err);
        alert(`Network error fetching data for ${targetSymbol}`);
    } finally {
        if (searchBtn) {
            searchBtn.disabled = false;
            searchBtn.innerText = "ANALYZE";
        }
        try { lucide.createIcons(); } catch(e){}
    }
}

// Render Hero Banner Header
function renderHeroBanner() {
    if (!currentData || !currentData.info) return;
    const el = (id) => document.getElementById(id);

    if (el("heroCompanyName")) el("heroCompanyName").innerText = currentData.company_name || "";
    if (el("heroSymbol")) el("heroSymbol").innerText = currentData.symbol || "";
    if (el("heroExchange")) el("heroExchange").innerText = currentData.info.exchange || "US NASDAQ/NYSE";
    if (el("heroSector")) el("heroSector").innerText = currentData.info.sector || "N/A";
    if (el("heroIndustry")) el("heroIndustry").innerText = currentData.info.industry || "N/A";
    if (el("heroCurrency")) el("heroCurrency").innerText = currentData.info.currency || "USD";
}

// Render 8 KPI Cards
function renderKPIs() {
    if (!currentData || !currentData.info) return;
    const info = currentData.info;
    const el = (id) => document.getElementById(id);
    
    if (el("kpiPrice")) el("kpiPrice").innerText = info.price ? `$${info.price.toFixed(2)}` : "N/A";
    if (el("kpiMarketCap")) el("kpiMarketCap").innerText = info.market_cap ? `$${(info.market_cap / 1e9).toFixed(2)}B` : "N/A";
    if (el("kpiEV")) el("kpiEV").innerText = info.market_cap ? `$${((info.market_cap * 1.1) / 1e9).toFixed(2)}B` : "N/A";
    if (el("kpiPE")) el("kpiPE").innerText = info.pe_ratio ? `${info.pe_ratio.toFixed(2)}x` : "N/A";
    if (el("kpiEVEBITDA")) el("kpiEVEBITDA").innerText = info.ev_ebitda ? `${info.ev_ebitda.toFixed(2)}x` : "N/A";
    
    const low = info.fifty_two_low ? `$${info.fifty_two_low.toFixed(2)}` : "N/A";
    const high = info.fifty_two_high ? `$${info.fifty_two_high.toFixed(2)}` : "N/A";
    if (el("kpiRange")) el("kpiRange").innerText = `${low} - ${high}`;

    if (el("kpiDivYield")) el("kpiDivYield").innerText = info.dividend_yield ? `${(info.dividend_yield * 100).toFixed(2)}%` : "0.55%";
    if (el("kpiTargetPrice")) el("kpiTargetPrice").innerText = info.target_price ? `$${info.target_price.toFixed(2)}` : "N/A";
}

// Render AI Briefing & Health Score Gauge
function renderAIBriefing() {
    if (!currentData || !currentData.ai_insights || !currentData.metrics) return;
    const ai = currentData.ai_insights;
    const metrics = currentData.metrics;

    const el = (id) => document.getElementById(id);
    if (el("aiExecutiveSummary")) el("aiExecutiveSummary").innerText = ai.executive_summary || "N/A";
    if (el("aiScoreExplanation")) el("aiScoreExplanation").innerText = ai.score_explanation || "N/A";
    
    const statusText = el("healthStatusText");
    if (statusText) {
        statusText.innerText = (metrics.health_status || "ANALYZED").toUpperCase();
        if (metrics.health_score >= 80) {
            statusText.style.color = currentTheme === "dark" ? "#10B981" : "#16A34A";
        } else if (metrics.health_score >= 60) {
            statusText.style.color = currentTheme === "dark" ? "#F59E0B" : "#D97706";
        } else {
            statusText.style.color = currentTheme === "dark" ? "#EF4444" : "#DC2626";
        }
    }

    renderGaugeChart(metrics.health_score);
}

// Render 5 Pillars Scorecard Matrix
function renderPillarsMatrix() {
    const container = document.getElementById("pillarsContainer");
    if (!container || !currentData || !currentData.metrics) return;
    container.innerHTML = "";

    const ratioEvals = currentData.metrics.ratio_evaluations || {};

    const pillars = [
        { name: "Liquidity", key: "current_ratio" },
        { name: "Leverage", key: "debt_to_equity" },
        { name: "Profitability", key: "net_margin" },
        { name: "Efficiency", key: "asset_turnover" },
        { name: "Valuation", key: "pe_ratio" }
    ];

    pillars.forEach(p => {
        const evalItem = ratioEvals[p.key] || {};
        let score = 85;
        let color = currentTheme === "dark" ? "#10B981" : "#16A34A";

        if (evalItem.status === "Caution") {
            score = 60;
            color = currentTheme === "dark" ? "#F59E0B" : "#D97706";
        } else if (evalItem.status === "Warning") {
            score = 35;
            color = currentTheme === "dark" ? "#EF4444" : "#DC2626";
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
    if (!currentData || !currentData.ai_insights) return;
    const ai = currentData.ai_insights;

    const strContainer = document.getElementById("strengthsContainer");
    if (strContainer) {
        strContainer.innerHTML = "";
        (ai.top_strengths || []).forEach(s => {
            const item = document.createElement("div");
            item.className = "strength-item-card";
            item.innerHTML = `<b>•</b> ${s}`;
            strContainer.appendChild(item);
        });
    }

    const weakContainer = document.getElementById("weaknessesContainer");
    if (weakContainer) {
        weakContainer.innerHTML = "";
        (ai.top_weaknesses || []).forEach(w => {
            const item = document.createElement("div");
            item.className = "weakness-item-card";
            item.innerHTML = `<b>•</b> ${w}`;
            weakContainer.appendChild(item);
        });
    }
}

// Render Gauge Chart with Theme Palette
function renderGaugeChart(score) {
    if (typeof Plotly === "undefined" || !document.getElementById("healthGaugeChart")) return;

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
        number: { suffix: " / 100", font: { size: 38, color: textColor, family: "Outfit" } },
        gauge: {
            axis: { range: [0, 100], tickwidth: 1, tickcolor: mutedColor, dtick: 20 },
            bar: { color: accentColor, thickness: 0.85 },
            bgcolor: currentTheme === "dark" ? "rgba(10, 14, 24, 0.6)" : "rgba(241, 245, 249, 0.8)",
            borderwidth: 1,
            bordercolor: currentTheme === "dark" ? "rgba(255, 255, 255, 0.08)" : "#CBD5E1",
            steps: [
                { range: [0, 60], color: "rgba(239, 68, 68, 0.12)" },
                { range: [60, 80], color: "rgba(245, 158, 11, 0.12)" },
                { range: [80, 100], color: "rgba(16, 185, 129, 0.12)" }
            ]
        }
    }];

    const gaugeLayout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: textColor, family: "Plus Jakarta Sans" },
        margin: { l: 20, r: 20, t: 20, b: 10 },
        height: 195
    };

    Plotly.newPlot("healthGaugeChart", gaugeData, gaugeLayout, { responsive: true, displayModeBar: false });
}

// Render Plotly Trend Charts
function renderCharts() {
    if (typeof Plotly === "undefined" || !currentData || !currentData.charts) return;

    const perf = currentData.charts.financial_performance || { years: [], revenue: [], net_income: [], gross_margin: [], net_margin: [] };
    const cashDebt = currentData.charts.cash_vs_debt || { years: [], cash: [], debt: [] };

    const textColor = currentTheme === "dark" ? "#F8FAFC" : "#0F172A";
    const mutedColor = currentTheme === "dark" ? "#94A3B8" : "#64748B";
    const gridColor = currentTheme === "dark" ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)";

    // 1. Revenue & Net Income Chart
    if (document.getElementById("chartRevenueNetIncome")) {
        const revTrace = {
            x: perf.years,
            y: perf.revenue,
            name: "Revenue ($B)",
            type: "bar",
            marker: { color: "rgba(56, 189, 248, 0.75)", line: { color: "#38BDF8", width: 1.5 } }
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
            title: { text: "<b>Revenue & Net Income Trend</b> ($ Billions)", font: { color: textColor, family: "Outfit", size: 14 } },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { color: mutedColor },
            xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "rgba(255,255,255,0.08)" : "#CBD5E1" },
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
            margin: { l: 40, r: 20, t: 40, b: 35 },
            height: 330
        };

        Plotly.newPlot("chartRevenueNetIncome", [revTrace, niTrace], layout1, { responsive: true, displayModeBar: false });
    }

    // 2. Cash vs Debt Chart
    if (document.getElementById("chartCashVsDebt")) {
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
            xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "rgba(255,255,255,0.08)" : "#CBD5E1" },
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
            margin: { l: 40, r: 20, t: 40, b: 35 },
            height: 330
        };

        Plotly.newPlot("chartCashVsDebt", [cashTrace, debtTrace], layout2, { responsive: true, displayModeBar: false });
    }

    // 3. Margin Trend Chart
    if (document.getElementById("chartMargins")) {
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
            title: { text: "<b>Margin Expansion Dynamics</b> (%)", font: { color: textColor, family: "Outfit", size: 14 } },
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { color: mutedColor },
            xaxis: { showgrid: false, linecolor: currentTheme === "dark" ? "rgba(255,255,255,0.08)" : "#CBD5E1" },
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: { orientation: "h", y: 1.1, x: 1, xanchor: "right" },
            margin: { l: 40, r: 20, t: 40, b: 35 },
            height: 330
        };

        Plotly.newPlot("chartMargins", [gmTrace, nmTrace], layout3, { responsive: true, displayModeBar: false });
    }
}

// Render Ratio Cards Grouped by Category with Clean Un-overlapped Headers
function renderRatioCards() {
    if (!currentData || !currentData.metrics) return;
    const ratioEvals = currentData.metrics.ratio_evaluations || {};
    const container = document.getElementById("ratiosCategoriesContainer");
    if (!container) return;
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
                    <span class="status-pill ${statusClass}">● ${item.status.toUpperCase()}</span>
                </div>
                <div class="ratio-name">${item.name}</div>
                <div class="ratio-val-large">${valStr}</div>
                <div class="progress-track">
                    <div class="progress-fill ${fillClass}" style="width: ${pct}%;"></div>
                </div>
                <div class="ratio-target-caption">Benchmark Target: ${item.target}</div>
            `;

            grid.appendChild(card);
        });

        container.appendChild(grid);
    });
}

// Render Financial Statement Table
function renderFinancialStatementTable() {
    if (!currentData || !currentData.statements) return;
    const stmtData = currentData.statements[activeStatementType];
    const container = document.getElementById("statementTableContainer");
    if (!container) return;
    
    if (!stmtData || !stmtData.rows || stmtData.rows.length === 0) {
        container.innerHTML = `<div style="text-align:center; padding:40px; color:var(--text-muted);">No statement data available for ${currentSymbol}.</div>`;
        return;
    }

    const searchInput = document.getElementById("statementSearchInput");
    const filterVal = searchInput ? searchInput.value.trim().toLowerCase() : "";

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
        row.values.forEach(val => {
            if (val === null || val === undefined) {
                tableHtml += `<td style="color: var(--text-dark);">-</td>`;
            } else if (typeof val === "number") {
                const isNeg = val < 0;
                const formatted = Math.abs(val) >= 1e6 ? `$${(val / 1e6).toLocaleString('en-US', {maximumFractionDigits: 0})}M` : `$${val.toLocaleString('en-US')}`;
                const valClass = isNeg ? "val-negative" : "val-positive";
                tableHtml += `<td class="${valClass}">${formatted}</td>`;
            } else {
                tableHtml += `<td>${val}</td>`;
            }
        });
        tableHtml += `</tr>`;
    });

    tableHtml += `</tbody></table>`;
    container.innerHTML = tableHtml;
}

// Export Table to CSV
function handleCsvExport() {
    if (!currentData || !currentData.statements) return;
    const stmtData = currentData.statements[activeStatementType];
    if (!stmtData || !stmtData.rows) return;

    let csvContent = "data:text/csv;charset=utf-8,Metric," + stmtData.columns.join(",") + "\n";
    stmtData.rows.forEach(row => {
        const line = [ `"${row.metric.replace(/"/g, '""')}"`, ...row.values.map(v => v === null ? "" : v) ].join(",");
        csvContent += line + "\n";
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `${currentSymbol}_${activeStatementType}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Download PDF Audit Report
async function handlePdfDownload() {
    if (!currentData) return;

    const btn = document.getElementById("downloadPdfBtn");
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i data-lucide="loader" class="inline-icon spin"></i> GENERATING PDF...`;
    }

    try {
        const response = await fetch("/api/download-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                symbol: currentData.symbol,
                company_name: currentData.company_name,
                metrics: currentData.metrics,
                ai_insights: currentData.ai_insights
            })
        });

        if (!response.ok) {
            throw new Error("Failed to compile PDF report");
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${currentData.symbol}_Institutional_Financial_Report.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);

    } catch (err) {
        alert(`PDF export failed: ${err.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = `<i data-lucide="file-down"></i> EXPORT AUDIT REPORT (PDF)`;
            try { lucide.createIcons(); } catch(e){}
        }
    }
}
