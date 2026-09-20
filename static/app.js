// Global State
let currentSymbol = "AAPL";
let currentData = null;
let activeStatementType = "income_statement";
let currentTheme = document.documentElement.getAttribute("data-theme") || "light";
let analysisProgressToken = 0;
let analysisProgressTimers = [];
let analysisProgressClock = null;
let analysisProgressStartedAt = 0;
let workspaceInitialized = false;

function initializeWorkspace() {
    if (workspaceInitialized) return;
    workspaceInitialized = true;
    try { fetchPresets(); } catch(e){}
    loadTickerData("AAPL");
}

function showExperienceView(view, updateHistory = false) {
    const intro = document.getElementById("introPage");
    const workspace = document.getElementById("researchWorkspace");
    const showWorkspace = view === "workspace";
    if (!intro || !workspace) return;

    intro.hidden = showWorkspace;
    workspace.hidden = !showWorkspace;
    document.body.classList.toggle("intro-active", !showWorkspace);

    if (updateHistory) {
        const nextUrl = showWorkspace ? "#workspace" : window.location.pathname;
        window.history.pushState({ statementiqView: view }, "", nextUrl);
    }

    window.scrollTo({ top: 0, behavior: "auto" });
    if (showWorkspace) {
        initializeWorkspace();
        window.requestAnimationFrame(() => window.dispatchEvent(new Event("resize")));
    }
}

function setupExperienceGate() {
    document.querySelectorAll("[data-open-workspace]").forEach(button => {
        button.addEventListener("click", () => showExperienceView("workspace", true));
    });

    window.addEventListener("popstate", () => {
        showExperienceView(window.location.hash === "#workspace" ? "workspace" : "intro");
    });

    showExperienceView(window.location.hash === "#workspace" ? "workspace" : "intro");
}

function themeColor(variable, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(variable).trim();
    return value || fallback;
}

function scoreColor(score) {
    if (!Number.isFinite(Number(score))) return themeColor("--text-dark", "#717a71");
    if (score < 60) return themeColor("--accent-red", "#ed8d87");
    if (score < 80) return themeColor("--accent-amber", "#e7c26f");
    return themeColor("--accent-green", "#83dca5");
}

function clearAnalysisProgressTimers() {
    analysisProgressTimers.forEach(timer => window.clearTimeout(timer));
    analysisProgressTimers = [];
    if (analysisProgressClock) {
        window.clearInterval(analysisProgressClock);
        analysisProgressClock = null;
    }
}

function formatElapsed(milliseconds) {
    const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = String(totalSeconds % 60).padStart(2, "0");
    return `${minutes}:${seconds} elapsed`;
}

function updateAnalysisProgress(progress, status, state = "active") {
    const panel = document.getElementById("analysisProgress");
    const fill = document.getElementById("analysisProgressFill");
    const statusEl = document.getElementById("analysisProgressStatus");
    const track = document.getElementById("analysisProgressTrack");
    if (!panel || !fill || !statusEl || !track) return;

    panel.classList.toggle("is-complete", state === "complete");
    panel.classList.toggle("is-error", state === "error");
    fill.style.width = `${Math.min(100, Math.max(0, progress))}%`;
    statusEl.textContent = status;
    track.setAttribute("aria-valuetext", status);
}

function scheduleAnalysisProgress(token, delay, progress, status) {
    const timer = window.setTimeout(() => {
        if (token !== analysisProgressToken) return;
        updateAnalysisProgress(progress, status);
    }, delay);
    analysisProgressTimers.push(timer);
}

function startAnalysisProgress(symbol) {
    clearAnalysisProgressTimers();
    const token = ++analysisProgressToken;
    const panel = document.getElementById("analysisProgress");
    const title = document.getElementById("analysisProgressTitle");
    const elapsed = document.getElementById("analysisProgressElapsed");
    if (!panel || !title || !elapsed) return token;

    analysisProgressStartedAt = Date.now();
    title.textContent = `Analyzing ${symbol}`;
    elapsed.textContent = "0:00 elapsed";
    panel.classList.remove("is-complete", "is-error");
    panel.classList.add("is-visible");
    panel.setAttribute("aria-hidden", "false");
    updateAnalysisProgress(8, "Connecting to the financial engine…");

    analysisProgressClock = window.setInterval(() => {
        if (token !== analysisProgressToken) return;
        elapsed.textContent = formatElapsed(Date.now() - analysisProgressStartedAt);
    }, 1000);

    scheduleAnalysisProgress(token, 1200, 20, "Connecting to secure financial data sources…");
    scheduleAnalysisProgress(token, 4000, 36, "Retrieving reported financial statements…");
    scheduleAnalysisProgress(token, 10000, 52, "Running ratio and valuation checks…");
    scheduleAnalysisProgress(token, 18000, 65, "Building the financial health assessment…");
    scheduleAnalysisProgress(token, 30000, 74, "The financial engine may be waking up — the first analysis can take longer.");
    scheduleAnalysisProgress(token, 48000, 84, "Still working — keeping the financial request open…");
    scheduleAnalysisProgress(token, 70000, 90, "Final checks are taking longer than usual…");
    return token;
}

function completeAnalysisProgress(token) {
    if (token !== analysisProgressToken) return;
    clearAnalysisProgressTimers();
    const panel = document.getElementById("analysisProgress");
    const elapsed = document.getElementById("analysisProgressElapsed");
    if (!panel) return;

    if (elapsed) elapsed.textContent = formatElapsed(Date.now() - analysisProgressStartedAt);
    updateAnalysisProgress(100, "Analysis complete. Dashboard updated.", "complete");
    const hideTimer = window.setTimeout(() => {
        if (token !== analysisProgressToken) return;
        panel.classList.remove("is-visible");
        panel.setAttribute("aria-hidden", "true");
    }, 1800);
    analysisProgressTimers.push(hideTimer);
}

function failAnalysisProgress(token, message) {
    if (token !== analysisProgressToken) return;
    clearAnalysisProgressTimers();
    const panel = document.getElementById("analysisProgress");
    const elapsed = document.getElementById("analysisProgressElapsed");
    if (!panel) return;

    if (elapsed) elapsed.textContent = "Not completed";
    updateAnalysisProgress(100, message, "error");
    const hideTimer = window.setTimeout(() => {
        if (token !== analysisProgressToken) return;
        panel.classList.remove("is-visible");
        panel.setAttribute("aria-hidden", "true");
    }, 9000);
    analysisProgressTimers.push(hideTimer);
}

// Initialize Application
function initApp() {
    const storedTheme = localStorage.getItem("statementiq-theme");
    if (storedTheme === "light" || storedTheme === "dark") {
        currentTheme = storedTheme;
        document.documentElement.setAttribute("data-theme", currentTheme);
    }
    const initialThemeIcon = document.getElementById("themeIcon");
    if (initialThemeIcon) {
        initialThemeIcon.setAttribute("data-lucide", currentTheme === "dark" ? "sun" : "moon");
    }
    try { lucide.createIcons(); } catch(e){}
    setupEventListeners();
    setupExperienceGate();
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
            localStorage.setItem("statementiq-theme", currentTheme);
            
            const themeIcon = document.getElementById("themeIcon");
            if (themeIcon) {
                themeIcon.setAttribute("data-lucide", currentTheme === "dark" ? "sun" : "moon");
                try { lucide.createIcons(); } catch(e){}
            }

            if (currentData) {
                try { renderAIBriefing(); } catch(e){}
                try { renderPillarsMatrix(); } catch(e){}
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
            ribbon.innerHTML = `<span class="ribbon-label"><i data-lucide="scan-search" class="inline-icon"></i> COVERAGE UNIVERSE</span>`;
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
    const progressToken = startAnalysisProgress(targetSymbol);

    if (searchBtn) {
        searchBtn.disabled = true;
        searchBtn.innerText = "Analyzing…";
    }

    try {
        let url = `/api/analyze?ticker=${encodeURIComponent(targetSymbol)}`;

        const res = await fetch(url);
        if (!res.ok) {
            let detail = `We could not complete the analysis for ${targetSymbol}. Please try again.`;
            try {
                const errData = await res.json();
                if (errData.detail) detail = errData.detail;
            } catch (error) {
                console.error("Unable to read analysis error response:", error);
            }
            failAnalysisProgress(progressToken, detail);
            return;
        }

        currentData = await res.json();
        currentSymbol = currentData.symbol;
        updateAnalysisProgress(94, "Preparing the dashboard…");

        // Render UI Sections smoothly with isolation
        try { renderHeroBanner(); } catch(e){ console.error("Hero render error:", e); }
        try { renderKPIs(); } catch(e){ console.error("KPI render error:", e); }
        try { renderAIBriefing(); } catch(e){ console.error("AI Briefing render error:", e); }
        try { renderPillarsMatrix(); } catch(e){ console.error("Pillars render error:", e); }
        try { renderStrengthsWeaknesses(); } catch(e){ console.error("Strengths render error:", e); }
        try { renderCharts(); } catch(e){ console.error("Charts render error:", e); }
        try { renderRatioCards(); } catch(e){ console.error("Ratio Cards render error:", e); }
        try { renderFinancialStatementTable(); } catch(e){ console.error("Statement Table render error:", e); }
        completeAnalysisProgress(progressToken);

    } catch (err) {
        console.error("Error loading ticker data:", err);
        failAnalysisProgress(
            progressToken,
            `The connection was interrupted while analyzing ${targetSymbol}. Please try again.`
        );
    } finally {
        if (searchBtn) {
            searchBtn.disabled = false;
            searchBtn.innerText = "Run analysis";
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
    if (el("heroExchange")) el("heroExchange").innerText = currentData.info.exchange || "N/A";
    if (el("heroSector")) el("heroSector").innerText = currentData.info.sector || "N/A";
    if (el("heroIndustry")) el("heroIndustry").innerText = currentData.info.industry || "N/A";
    if (el("heroCurrency")) el("heroCurrency").innerText = currentData.info.currency || "N/A";
    if (el("heroDataSource")) {
        const quality = currentData.data_quality || {};
        const provider = quality.statement_provider || quality.market_provider || "Source unavailable";
        let asOf = "timestamp unavailable";
        if (quality.market_data_as_of) {
            const parsed = new Date(quality.market_data_as_of);
            asOf = Number.isNaN(parsed.getTime()) ? quality.market_data_as_of : parsed.toLocaleString();
        }
        el("heroDataSource").innerText = `LIVE SOURCE · ${provider} · MARKET DATA ${asOf}`;
    }
}

// Render 8 KPI Cards
function renderKPIs() {
    if (!currentData || !currentData.info) return;
    const info = currentData.info;
    const el = (id) => document.getElementById(id);
    
    const valid = value => Number.isFinite(Number(value));
    if (el("kpiPrice")) el("kpiPrice").innerText = valid(info.price) ? `$${Number(info.price).toFixed(2)}` : "N/A";
    if (el("kpiMarketCap")) el("kpiMarketCap").innerText = valid(info.market_cap) ? `$${(Number(info.market_cap) / 1e9).toFixed(2)}B` : "N/A";
    if (el("kpiEV")) el("kpiEV").innerText = valid(info.enterprise_value) ? `$${(Number(info.enterprise_value) / 1e9).toFixed(2)}B` : "N/A";
    if (el("kpiPE")) el("kpiPE").innerText = valid(info.pe_ratio) ? `${Number(info.pe_ratio).toFixed(2)}x` : "N/A";
    if (el("kpiEVEBITDA")) el("kpiEVEBITDA").innerText = valid(info.ev_ebitda) ? `${Number(info.ev_ebitda).toFixed(2)}x` : "N/A";
    
    const low = valid(info.fifty_two_low) ? `$${Number(info.fifty_two_low).toFixed(2)}` : "N/A";
    const high = valid(info.fifty_two_high) ? `$${Number(info.fifty_two_high).toFixed(2)}` : "N/A";
    if (el("kpiRange")) el("kpiRange").innerText = `${low} - ${high}`;

    if (el("kpiDivYield")) el("kpiDivYield").innerText = valid(info.dividend_yield) ? `${(Number(info.dividend_yield) * 100).toFixed(2)}%` : "N/A";
    if (el("kpiTargetPrice")) el("kpiTargetPrice").innerText = valid(info.target_price) ? `$${Number(info.target_price).toFixed(2)}` : "N/A";
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
        statusText.innerText = (metrics.health_status || "INSUFFICIENT DATA").toUpperCase();
        statusText.style.color = scoreColor(metrics.health_score);
    }

    renderGaugeChart(metrics.health_score);
}

// Render 5 Pillars Scorecard Matrix
function renderPillarsMatrix() {
    const container = document.getElementById("pillarsContainer");
    if (!container || !currentData || !currentData.metrics) return;
    container.innerHTML = "";

    const ratioEvals = currentData.metrics.ratio_evaluations || {};

    const pillars = ["Liquidity", "Leverage", "Profitability", "Efficiency", "Valuation"];

    pillars.forEach(name => {
        const categoryItems = Object.values(ratioEvals).filter(item => item.category === name);
        const statuses = categoryItems.map(item => item.status);
        let status = "N/A";
        let color = themeColor("--accent-green", "#83dca5");
        if (statuses.includes("Warning")) {
            status = "Warning";
            color = themeColor("--accent-red", "#ed8d87");
        } else if (statuses.includes("Caution")) {
            status = "Caution";
            color = themeColor("--accent-amber", "#e7c26f");
        } else if (statuses.includes("Healthy")) {
            status = "Healthy";
        } else if (statuses.includes("N/M")) {
            status = "N/M";
            color = themeColor("--accent-amber", "#e7c26f");
        } else {
            color = themeColor("--text-dark", "#717a71");
        }

        const div = document.createElement("div");
        div.className = "pillar-item";
        div.innerHTML = `
            <span class="pillar-name">${name}</span>
            <div class="pillar-track">
                <div class="pillar-fill" style="width: ${status === 'N/A' ? 0 : 100}%; background: ${color};"></div>
            </div>
            <span class="pillar-val" style="color: ${color};">${status}</span>
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

    const textColor = themeColor("--text-main", "#f2f4ec");
    const mutedColor = themeColor("--text-dark", "#717a71");
    const panelColor = themeColor("--card-soft", "#111512");
    const riskColor = themeColor("--gauge-risk", "#f05e58");
    const cautionColor = themeColor("--gauge-caution", "#ff982b");
    const healthyColor = themeColor("--gauge-healthy", "#2ed477");

    if (!Number.isFinite(Number(score))) {
        Plotly.newPlot("healthGaugeChart", [], {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            xaxis: { visible: false },
            yaxis: { visible: false },
            annotations: [{
                text: "N/A<br><span style='font-size:11px'>INSUFFICIENT DATA</span>",
                x: 0.5, y: 0.5, showarrow: false, align: "center",
                font: { size: 28, color: mutedColor, family: "DM Mono" }
            }],
            margin: { l: 20, r: 20, t: 20, b: 10 },
            height: 195
        }, { responsive: true, displayModeBar: false });
        return;
    }

    const gaugeData = [{
        type: "indicator",
        mode: "gauge+number",
        value: score,
        domain: { x: [0, 1], y: [0, 1] },
        number: { suffix: " / 100", font: { size: 34, color: textColor, family: "DM Mono" } },
        gauge: {
            axis: {
                range: [0, 100],
                tickwidth: 0,
                tickcolor: "rgba(0,0,0,0)",
                tickfont: { color: textColor, size: 10, family: "DM Mono" },
                dtick: 20
            },
            bar: { color: "rgba(0,0,0,0)", thickness: 0.78 },
            bgcolor: panelColor,
            borderwidth: 0,
            steps: [
                { range: [0, 60], color: riskColor },
                { range: [60, 80], color: cautionColor },
                { range: [80, 100], color: healthyColor }
            ],
            threshold: {
                line: { color: textColor, width: 4 },
                thickness: 0.9,
                value: Number(score)
            }
        }
    }];

    const gaugeLayout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { color: textColor, family: "Manrope" },
        margin: { l: 20, r: 20, t: 20, b: 10 },
        height: 195
    };

    Plotly.newPlot("healthGaugeChart", gaugeData, gaugeLayout, { responsive: true, displayModeBar: false });
}

function formatInspectorValue(value, prefix = "", suffix = "") {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "N/A";
    return `${prefix}${Number(value).toFixed(1)}${suffix}`;
}

function bindChartInspector(chartId, inspectorId, years, rows) {
    const chart = document.getElementById(chartId);
    const inspector = document.getElementById(inspectorId);
    if (!chart || !inspector || !Array.isArray(years) || years.length === 0) return;

    const renderYear = index => {
        const year = years[index] || "N/A";
        inspector.innerHTML = `
            <span class="inspector-year">${year}</span>
            ${rows.map(row => `
                <span class="inspector-metric">
                    <i class="inspector-dot ${row.tone}"></i>
                    <span>${row.label}</span>
                    <strong>${formatInspectorValue(row.values[index], row.prefix || "", row.suffix || "")}</strong>
                </span>
            `).join("")}
        `;
    };

    renderYear(years.length - 1);
    if (typeof chart.removeAllListeners === "function") {
        chart.removeAllListeners("plotly_hover");
        chart.removeAllListeners("plotly_click");
    }
    const selectPoint = event => {
        const hoveredYear = event && event.points && event.points[0] ? String(event.points[0].x) : "";
        const index = years.map(String).indexOf(hoveredYear);
        if (index >= 0) renderYear(index);
    };
    if (typeof chart.on === "function") {
        chart.on("plotly_hover", selectPoint);
        chart.on("plotly_click", selectPoint);
    }
}

// Render Plotly Trend Charts
function renderCharts() {
    if (typeof Plotly === "undefined" || !currentData || !currentData.charts) return;

    const perf = currentData.charts.financial_performance || { years: [], revenue: [], net_income: [], gross_margin: [], net_margin: [] };
    const cashDebt = currentData.charts.cash_vs_debt || { years: [], cash: [], debt: [] };

    const textColor = themeColor("--text-main", "#f2f4ec");
    const mutedColor = themeColor("--text-dark", "#717a71");
    const gridColor = themeColor("--card-border", "rgba(226, 237, 222, 0.1)");
    const blue = themeColor("--accent-blue", "#9cbfff");
    const green = themeColor("--accent-green", "#83dca5");
    const red = themeColor("--accent-red", "#ed8d87");
    const purple = themeColor("--accent-purple", "#c5adff");
    const amber = themeColor("--accent-amber", "#e7c26f");
    const panelColor = themeColor("--card-bg", "#191a16");
    const legendLayout = {
        orientation: "h",
        x: 0,
        xanchor: "left",
        y: -0.2,
        yanchor: "top",
        font: { size: 11, color: mutedColor, family: "Manrope" },
        itemclick: "toggle",
        itemdoubleclick: "toggleothers"
    };
    const xAxisBase = {
        type: "category",
        showgrid: false,
        linecolor: gridColor,
        showspikes: true,
        spikecolor: themeColor("--chart-crosshair", "#d6dad1"),
        spikethickness: 1,
        spikedash: "solid",
        spikesnap: "cursor"
    };

    // 1. Revenue & Net Income Chart
    if (document.getElementById("chartRevenueNetIncome")) {
        const revTrace = {
            x: perf.years,
            y: perf.revenue,
            name: "Revenue ($B)",
            type: "bar",
            marker: { color: blue, opacity: 0.84, line: { color: blue, width: 1 } },
            hoverinfo: "none"
        };

        const niTrace = {
            x: perf.years,
            y: perf.net_income,
            name: "Net Income ($B)",
            type: "scatter",
            mode: "lines+markers",
            line: { color: green, width: 2.5, shape: "spline" },
            marker: { size: 7, color: green, line: { color: panelColor, width: 1.5 } },
            hoverinfo: "none"
        };

        const layout1 = {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { color: mutedColor },
            xaxis: xAxisBase,
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: legendLayout,
            hovermode: "x",
            hoverdistance: 50,
            spikedistance: -1,
            margin: { l: 48, r: 20, t: 20, b: 70 },
            height: 300
        };

        Plotly.newPlot("chartRevenueNetIncome", [revTrace, niTrace], layout1, { responsive: true, displayModeBar: false }).then(() => {
            bindChartInspector("chartRevenueNetIncome", "inspectorRevenue", perf.years, [
                { label: "Revenue", values: perf.revenue, prefix: "$", suffix: "B", tone: "blue" },
                { label: "Net income", values: perf.net_income, prefix: "$", suffix: "B", tone: "green" }
            ]);
        });
    }

    // 2. Cash vs Debt Chart
    if (document.getElementById("chartCashVsDebt")) {
        const cashTrace = {
            x: cashDebt.years,
            y: cashDebt.cash,
            name: "Cash & Equivalents",
            type: "bar",
            marker: { color: green, opacity: 0.86, line: { color: green, width: 1 } },
            hoverinfo: "none"
        };

        const debtTrace = {
            x: cashDebt.years,
            y: cashDebt.debt,
            name: "Total Debt Obligations",
            type: "bar",
            marker: { color: red, opacity: 0.84, line: { color: red, width: 1 } },
            hoverinfo: "none"
        };

        const layout2 = {
            barmode: "group",
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { color: mutedColor },
            xaxis: xAxisBase,
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: legendLayout,
            hovermode: "x",
            hoverdistance: 50,
            spikedistance: -1,
            margin: { l: 48, r: 20, t: 20, b: 70 },
            height: 300
        };

        Plotly.newPlot("chartCashVsDebt", [cashTrace, debtTrace], layout2, { responsive: true, displayModeBar: false }).then(() => {
            bindChartInspector("chartCashVsDebt", "inspectorCashDebt", cashDebt.years, [
                { label: "Cash", values: cashDebt.cash, prefix: "$", suffix: "B", tone: "green" },
                { label: "Debt", values: cashDebt.debt, prefix: "$", suffix: "B", tone: "red" }
            ]);
        });
    }

    // 3. Margin Trend Chart
    if (document.getElementById("chartMargins")) {
        const gmTrace = {
            x: perf.years,
            y: perf.gross_margin,
            name: "Gross Margin (%)",
            type: "scatter",
            mode: "lines+markers",
            line: { color: purple, width: 2.5, shape: "spline" },
            marker: { size: 8, color: purple, line: { color: panelColor, width: 1.5 } },
            hoverinfo: "none"
        };

        const nmTrace = {
            x: perf.years,
            y: perf.net_margin,
            name: "Net Profit Margin (%)",
            type: "scatter",
            mode: "lines+markers",
            line: { color: amber, width: 2.5, shape: "spline" },
            marker: { size: 8, color: amber, line: { color: panelColor, width: 1.5 } },
            hoverinfo: "none"
        };

        const layout3 = {
            paper_bgcolor: "rgba(0,0,0,0)",
            plot_bgcolor: "rgba(0,0,0,0)",
            font: { color: mutedColor },
            xaxis: xAxisBase,
            yaxis: { showgrid: true, gridcolor: gridColor },
            legend: legendLayout,
            hovermode: "x",
            hoverdistance: 50,
            spikedistance: -1,
            margin: { l: 48, r: 20, t: 20, b: 70 },
            height: 300
        };

        Plotly.newPlot("chartMargins", [gmTrace, nmTrace], layout3, { responsive: true, displayModeBar: false }).then(() => {
            bindChartInspector("chartMargins", "inspectorMargins", perf.years, [
                { label: "Gross margin", values: perf.gross_margin, suffix: "%", tone: "purple" },
                { label: "Net profit", values: perf.net_margin, suffix: "%", tone: "amber" }
            ]);
        });
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

    const categoryDescriptions = {
        Liquidity: "Short-term obligations",
        Leverage: "Capital structure and debt",
        Profitability: "Earnings quality and returns",
        Efficiency: "Asset utilization",
        Valuation: "Market expectations"
    };

    Object.entries(categories).forEach(([catName, items], categoryIndex) => {
        const section = document.createElement("section");
        section.className = "ratio-category-section";
        section.dataset.category = catName.toLowerCase().replace(/[^a-z0-9]+/g, "-");

        const catHeader = document.createElement("div");
        catHeader.className = "category-title";
        catHeader.innerHTML = `
            <span class="category-index">${String(categoryIndex + 1).padStart(2, "0")}</span>
            <span class="category-copy">
                <strong>${catName}</strong>
                <small>${categoryDescriptions[catName] || "Financial diagnostics"}</small>
            </span>
            <span class="category-count">${items.length} ${items.length === 1 ? "metric" : "metrics"}</span>
        `;
        section.appendChild(catHeader);

        const grid = document.createElement("div");
        grid.className = "ratio-cards-grid";

        items.forEach(item => {
            const card = document.createElement("div");
            card.className = "ratio-card";

            let statusClass = "healthy";
            if (item.status === "Caution") {
                statusClass = "caution";
            } else if (item.status === "Warning") {
                statusClass = "warning";
            } else if (item.status === "N/M") {
                statusClass = "nm";
            } else if (item.status === "N/A") {
                statusClass = "na";
            }

            let valStr = item.status === "N/M" ? "N/M" : "N/A";
            if (item.value !== null && item.value !== undefined && !isNaN(item.value)) {
                if (item.format === "{:.1%}") {
                    valStr = `${(item.value * 100).toFixed(1)}%`;
                } else {
                    valStr = item.value.toFixed(2);
                }
            }

            card.innerHTML = `
                <div class="ratio-card-header">
                    <span class="status-pill ${statusClass}">● ${item.status.toUpperCase()}</span>
                </div>
                <div class="ratio-name">${item.name}</div>
                <div class="ratio-val-large">${valStr}</div>
                <div class="ratio-target-caption">Benchmark Target: ${item.target}</div>
            `;

            grid.appendChild(card);
        });
        section.appendChild(grid);
        container.appendChild(section);
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
            btn.innerHTML = `<i data-lucide="file-down"></i> Download research report`;
            try { lucide.createIcons(); } catch(e){}
        }
    }
}
