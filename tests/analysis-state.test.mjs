import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const client = readFileSync(new URL("../static/request-client.js", import.meta.url), "utf8");
const app = readFileSync(new URL("../static/app.js", import.meta.url), "utf8");

function createFrontend() {
    const nodes = new Map();
    function element(id) {
        if (!nodes.has(id)) nodes.set(id, {
            hidden: false, disabled: false, textContent: "", innerText: "", style: {},
            classList: { add() {}, remove() {}, toggle() {} },
            setAttribute() {}, getAttribute() {},
            listeners: {}, addEventListener(type,fn) {this.listeners[type]=fn;},
        });
        return nodes.get(id);
    }
    const context = vm.createContext({
        document: {
            readyState: "loading", documentElement: { getAttribute: () => "light" },
            addEventListener() {}, querySelectorAll: () => [], getElementById: element,
        },
        window: {
            location: {search:''},
            setTimeout: () => 1, clearTimeout() {}, setInterval: () => 1, clearInterval() {},
            requestAnimationFrame: fn => fn(), dispatchEvent() {},
        },
        console: { error() {} }, Date, AbortController, DOMException, Event, URLSearchParams,
    });
    vm.runInContext(`${client}\n${app}\n globalThis.frontend = {
        loadTickerData, loadFilingTextReview, setupEventListeners, initializeWorkspace, getData: () => currentData, getSymbol: () => currentSymbol,
        client: StatementIQRequests,
    };`, context);
    // Isolate the request/state logic from Plotly and detailed financial rendering.
    vm.runInContext(`
        renderHeroBanner = renderKPIs = renderAIBriefing = renderPillarsMatrix =
        renderStrengthsWeaknesses = renderCharts = renderRatioCards = renderSupportingAnalysis =
        renderStatementAnalysis = renderSectorAnalysis = renderFilingReview = renderFinancialStatementTable = () => {};
    `, context);
    const pending = [];
    context.frontend.client.requestJson = (url, options) => new Promise((resolve, reject) => {
        pending.push({ url, options, resolve, reject });
        options.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")), { once: true });
    });
    return { frontend: context.frontend, element, pending };
}

function data(symbol) {
    return { symbol, info: { price: 123.45 }, metrics: {}, data_quality: { fetched_at: "2026-11-02T16:00:00Z" } };
}

test("opening the workspace starts waking immediately without delaying the automatic Apple request", async () => {
    const h = createFrontend();
    let startupRequests = 0;
    h.frontend.client.beginVisit = () => { startupRequests += 1; return new Promise(() => {}); };
    h.frontend.initializeWorkspace();
    h.frontend.initializeWorkspace();
    assert.equal(startupRequests, 1);
    assert.equal(h.pending.length, 2);
    assert.equal(h.pending[0].url, "/api/presets");
    assert.match(h.pending[1].url, /ticker=AAPL&refresh=false/);
    assert.equal(h.pending[0].options.startupRecovery, true);
    assert.equal(h.pending[1].options.startupRecovery, true);
    h.pending[0].resolve({ presets: {} });
    h.pending[1].resolve(data("AAPL"));
    await h.frontend.loadTickerData("AAPL");
    assert.equal(h.frontend.getSymbol(), "AAPL");
});

test("a direct workspace visit can start the engine before external chart downloads", () => {
    const html = readFileSync(new URL("../static/index.html", import.meta.url), "utf8");
    const requestScript = html.indexOf('src="/static/request-client.js?');
    const earlyVisit = html.indexOf('void StatementIQRequests.beginVisit()');
    const charts = html.indexOf('src="https://cdn.plot.ly/');
    assert.ok(requestScript >= 0 && requestScript < earlyVisit && earlyVisit < charts);
    assert.ok(earlyVisit < html.indexOf('href="https://fonts.googleapis.com/css2'));
    assert.equal((html.match(/src="\/static\/request-client\.js\?/g) || []).length, 1);
    assert.match(html.slice(requestScript, charts), /window.location.hash === "#workspace"/);
});

test('normal searches reuse fresh data and the explicit refresh button bypasses it',async()=>{
    const h=createFrontend();h.frontend.setupEventListeners();
    h.element('tickerSearchInput').value='EXAMPLE';h.element('searchBtn').listeners.click();
    assert.match(h.pending[0].url,/refresh=false/);
    h.pending[0].resolve(data('EXAMPLE'));await h.frontend.loadTickerData('EXAMPLE');
    h.element('refreshDataBtn').listeners.click();
    assert.match(h.pending[1].url,/refresh=true/);
    h.pending[1].resolve(data('EXAMPLE'));await h.frontend.loadTickerData('EXAMPLE');
});

test("first-load failure hides the entire financial dashboard and leaves a retryable error", async () => {
    const h = createFrontend();
    const request = h.frontend.loadTickerData("AAPL");
    assert.equal(h.element("mainDashboard").hidden, true);
    assert.equal(h.element("downloadPdfBtn").disabled, true);
    h.pending[0].reject(new h.frontend.client.RequestError("Service unavailable", { retryable: true }));
    await request;
    assert.equal(h.frontend.getData(), null);
    assert.equal(h.element("mainDashboard").hidden, true);
    assert.equal(h.element("analysisEmptyState").hidden, false);
    assert.match(h.element("analysisEmptyMessage").textContent, /temporarily unavailable/);
    assert.equal(h.element("searchBtn").disabled, false);
});

test('annual text review is separate and an old company response cannot overwrite a new analysis',async()=>{
    const h=createFrontend(), first=h.frontend.loadTickerData('AAPL');
    const apple={...data('AAPL'),filing_disclosure_review:{status:'deferred'},data_quality:{sec_filing:{key_filings:{annual:{filing_url:'https://www.sec.gov/apple.htm'}}}}};
    h.pending[0].resolve(apple);await first;
    const review=h.frontend.loadFilingTextReview();
    assert.match(h.pending[1].url,/filing-review/);
    const next=h.frontend.loadTickerData('MSFT');h.pending[2].resolve(data('MSFT'));await next;
    h.pending[1].resolve({symbol:'AAPL',filing_url:'https://www.sec.gov/apple.htm',review:{status:'analyzed'}});await review;
    assert.equal(h.frontend.getData().symbol,'MSFT');
    assert.equal(h.frontend.getData().filing_disclosure_review,undefined);
});

test("repeated submissions of the same running ticker share one request", async () => {
    const h = createFrontend();
    const first = h.frontend.loadTickerData("aapl");
    const second = h.frontend.loadTickerData("AAPL");
    assert.equal(first, second);
    assert.equal(h.pending.length, 1);
    h.pending[0].resolve(data("AAPL"));
    await first;
    assert.equal(h.element("mainDashboard").hidden, false);
    assert.equal(h.element("analysisEmptyState").hidden, true);
    assert.equal(h.element("downloadPdfBtn").disabled, false);
});

test("switching tickers cancels the superseded request and only renders the new ticker", async () => {
    const h = createFrontend();
    const first = h.frontend.loadTickerData("AAPL");
    const second = h.frontend.loadTickerData("MSFT");
    assert.equal(h.pending[0].options.signal.aborted, true);
    await first;
    assert.equal(h.element("searchBtn").disabled, true);
    h.pending[1].resolve(data("MSFT"));
    await second;
    assert.equal(h.frontend.getSymbol(), "MSFT");
    assert.equal(h.frontend.getData().symbol, "MSFT");
    assert.equal(h.element("searchBtn").disabled, false);
});

test("failed analysis for a new ticker labels the prior company's completed result", async () => {
    const h = createFrontend();
    const first = h.frontend.loadTickerData("AAPL");
    h.pending[0].resolve(data("AAPL"));
    await first;
    const second = h.frontend.loadTickerData("NVDA");
    assert.match(h.element("analysisDataNoticeText").textContent, /Analyzing NVDA/);
    assert.match(h.element("analysisDataNoticeText").textContent, /last completed analysis for AAPL/);
    assert.equal(h.element("downloadPdfBtn").disabled, true);
    h.pending[1].reject(new h.frontend.client.RequestError("Busy", { retryable: true }));
    await second;
    assert.equal(h.frontend.getData().symbol, "AAPL");
    assert.equal(h.element("mainDashboard").hidden, false);
    assert.equal(h.element("analysisDataNotice").hidden, false);
    assert.match(h.element("analysisDataNoticeText").textContent, /unavailable for NVDA/);
    assert.match(h.element("analysisDataNoticeText").textContent, /last completed analysis for AAPL/);
});

test("invalid ticker messages remain visible and are not replaced with a hosting error", async () => {
    const h = createFrontend();
    const request = h.frontend.loadTickerData("INVALID");
    h.pending[0].reject(new h.frontend.client.RequestError("Ticker not found", { status: 400 }));
    await request;
    assert.equal(h.element("analysisEmptyMessage").textContent, "Ticker not found");
});

test("repeated transient failures request startup only once per analysis", async () => {
    const h = createFrontend();
    let startupRequests = 0;
    h.frontend.client.wakeService = () => { startupRequests += 1; return Promise.resolve(); };
    const request = h.frontend.loadTickerData("AAPL");
    h.pending[0].options.onRetry({ delayMs: 5000, status: 429 });
    h.pending[0].options.onRetry({ delayMs: 10000, status: 503 });
    assert.equal(startupRequests, 1);
    assert.equal(h.element("mainDashboard").hidden, true);
    h.pending[0].resolve(data("AAPL"));
    await request;
    assert.equal(h.frontend.getSymbol(), "AAPL");
});
