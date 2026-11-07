import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";
import worker from "../src/index.js";

const source = readFileSync(new URL("../static/request-client.js", import.meta.url), "utf8");

function harness(respond) {
    let now = Date.parse("2026-11-02T16:00:00Z");
    let sequence = 0;
    const timers = new Map();
    const calls = [];
    class Clock extends Date { static now() { return now; } }
    const context = vm.createContext({
        Date: Clock, AbortController, DOMException, URL,
        setTimeout: (fn, ms) => {
            const id = ++sequence;
            timers.set(id, { fn, at: now + ms });
            return id;
        },
        clearTimeout: id => timers.delete(id),
        fetch: async (url, options) => {
            calls.push({ url, at: now, options });
            return respond(calls.length, options, url);
        },
    });
    vm.runInContext(`${source}\nglobalThis.client = StatementIQRequests;`, context);
    return {
        client: context.client, calls, timers,
        async run(promise) {
            let done = false, value, error;
            promise.then(result => { value = result; done = true; }, err => { error = err; done = true; });
            for (let i = 0; i < 100 && !done; i += 1) {
                await new Promise(setImmediate);
                if (done) break;
                const next = [...timers.entries()].sort((a, b) => a[1].at - b[1].at)[0];
                assert.ok(next, "Pending request must have a timeout or backoff");
                now = next[1].at;
                timers.delete(next[0]);
                next[1].fn();
            }
            assert.ok(done, "Request must finish within the bounded recovery window");
            if (error) throw error;
            return value;
        },
    };
}

test("429 and 502 recover to real JSON, respecting Retry-After and increasing delays", async () => {
    const h = harness(n => n === 1
        ? new Response("Too Many Requests", { status: 429, headers: { "Retry-After": "7" } })
        : n === 2 ? new Response("Bad Gateway", { status: 502 })
            : Response.json({ symbol: "AAPL", price: 341.18 }));
    const notices = [];
    const result = await h.run(h.client.requestJson("/api/analyze", { onRetry: x => notices.push(x) }));
    assert.equal(result.price, 341.18);
    assert.equal(h.calls.length, 3);
    assert.ok(h.calls[1].at - h.calls[0].at >= 7000);
    assert.ok(h.calls[2].at - h.calls[1].at >= 3600);
    assert.deepEqual(notices.map(x => x.status), [429, 502]);
    assert.equal(h.timers.size, 0);
});

test("HTTP-date Retry-After is honored", async () => {
    const h = harness(n => n === 1 ? new Response("Busy", {
        status: 503, headers: { "Retry-After": "Mon, 02 Nov 2026 16:00:15 GMT" },
    }) : Response.json({ ok: true }));
    await h.run(h.client.requestJson("/api/test"));
    assert.ok(h.calls[1].at - h.calls[0].at >= 15000);
});

test("HTML startup pages and incomplete JSON payloads are not accepted as analysis data", async () => {
    const h = harness(n => n === 1 ? new Response("<html>Starting service</html>")
        : n === 2 ? Response.json({}) : Response.json({ symbol: "MSFT" }));
    const data = await h.run(h.client.requestJson("/api/test", { validate: x => x.symbol === "MSFT" }));
    assert.equal(data.symbol, "MSFT");
    assert.equal(h.calls.length, 3);
});

test("invalid ticker errors keep the actual message and are not retried", async () => {
    const h = harness(() => Response.json({ detail: "Ticker not found" }, { status: 400 }));
    await assert.rejects(h.run(h.client.requestJson("/api/test")), /Ticker not found/);
    assert.equal(h.calls.length, 1);
    assert.equal(h.timers.size, 0);
});

test("a broken network connection recovers", async () => {
    const h = harness(n => {
        if (n === 1) throw new TypeError("Failed to fetch");
        return Response.json({ ok: true });
    });
    assert.equal((await h.run(h.client.requestJson("/api/test"))).ok, true);
    assert.equal(h.calls.length, 2);
});

test("a stalled request times out, then retries without hanging forever", async () => {
    const h = harness((n, { signal }) => n === 1 ? new Promise((resolve, reject) => {
        signal.addEventListener("abort", () => reject(new DOMException("Timed out", "AbortError")), { once: true });
    }) : Response.json({ ok: true }));
    assert.equal((await h.run(h.client.requestJson("/api/test"))).ok, true);
    assert.ok(h.calls[1].at - h.calls[0].at >= 75000);
});

test("persistent failures stop after the allowed attempts", async () => {
    const h = harness(() => new Response("Unavailable", { status: 503 }));
    await assert.rejects(h.run(h.client.requestJson("/api/test")), /temporarily unavailable/);
    assert.equal(h.calls.length, 8);
    assert.ok(h.calls.at(-1).at - h.calls[0].at < 180000);
    assert.equal(h.timers.size, 0);
});

test("startup recovery stays alive through a cold start and detects readiness within five seconds", async () => {
    const h = harness(() => h.calls.at(-1).at - h.calls[0].at < 70000
        ? new Response("Starting", { status: 503 }) : Response.json({ symbol: "AAPL" }));
    const result = await h.run(h.client.requestJson("/api/analyze?ticker=AAPL", { startupRecovery: true }));
    assert.equal(result.symbol, "AAPL");
    const elapsed = h.calls.at(-1).at - h.calls[0].at;
    assert.ok(elapsed >= 70000 && elapsed <= 75000, `Readiness observed after ${elapsed}ms`);
    assert.ok(h.calls.length > 8, "Startup retries must not exhaust the old eight-attempt limit");
    for (let i = 1; i < h.calls.length; i += 1) {
        assert.ok(h.calls[i].at - h.calls[i - 1].at <= 5000);
    }
    assert.equal(h.timers.size, 0);
});

test("startup recovery still respects explicit cooldowns and rate-limit backoff", async () => {
    const h = harness(n => n === 1 ? new Response("Starting", {
        status: 503, headers: { "Retry-After": "20" },
    }) : n <= 5 ? new Response("Rate limited", { status: 429 }) : Response.json({ ok: true }));
    await h.run(h.client.requestJson("/api/analyze", { startupRecovery: true }));
    assert.ok(h.calls[1].at - h.calls[0].at >= 20000);
    assert.ok(h.calls[5].at - h.calls[4].at >= 27000);
    assert.equal(h.timers.size, 0);
});

test("persistent startup failures remain bounded by the recovery deadline", async () => {
    const h = harness(() => new Response("Starting", { status: 503 }));
    await assert.rejects(h.run(h.client.requestJson("/api/analyze", { startupRecovery: true })), /temporarily unavailable/);
    assert.ok(h.calls.length <= 36);
    assert.ok(h.calls.at(-1).at - h.calls[0].at < 180000);
    assert.equal(h.timers.size, 0);
});

test("early page startup and workspace initialization share one visitor request", async () => {
    const h = harness((n, options, url) => url === "/api/startup-config"
        ? Response.json({ startup_url: "https://backend.example.com/health" }) : new Response(null));
    const first = h.client.beginVisit();
    assert.equal(h.client.beginVisit(), first);
    await h.run(first);
    await h.client.beginVisit();
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].url, "https://backend.example.com/health");
    assert.equal(h.timers.size, 0);
});

test("a cooldown longer than the total budget is not ignored", async () => {
    const h = harness(() => new Response("Slow down", { status: 429, headers: { "Retry-After": "3600" } }));
    await assert.rejects(h.run(h.client.requestJson("/api/test")), /temporarily unavailable/);
    assert.equal(h.calls.length, 1);
});

test("cancelling during backoff stops all further requests", async () => {
    const h = harness(() => new Response("Slow down", { status: 429 }));
    const controller = new AbortController();
    const promise = h.client.requestJson("/api/test", {
        signal: controller.signal,
        onRetry: () => queueMicrotask(() => controller.abort()),
    });
    await assert.rejects(h.run(promise), error => error.name === "AbortError");
    assert.equal(h.calls.length, 1);
    assert.equal(h.timers.size, 0);
});

test("an already cancelled request never fetches", async () => {
    const h = harness(() => Response.json({ ok: true }));
    const controller = new AbortController();
    controller.abort();
    await assert.rejects(h.run(h.client.requestJson("/api/test", { signal: controller.signal })), error => error.name === "AbortError");
    assert.equal(h.calls.length, 0);
});

test("edge proxy returns retryable JSON and a traceable request ID for an upstream 429", async t => {
    const logs = [];
    let originTrace;
    t.mock.method(console, "error", value => logs.push(JSON.parse(value)));
    t.mock.method(globalThis, "fetch", async request => { originTrace = request.headers.get('x-statementiq-request-id'); return new Response("Too Many Requests", {
        status: 429, headers: { "retry-after": "12", "rndr-id": "origin-test-id" },
    }); });
    const response = await worker.fetch(new Request("https://statementiq-lb.com/api/analyze?ticker=AAPL", {headers:{'x-statementiq-request-id':'untrusted-client-trace'}}), {
        BACKEND_ORIGIN: "https://backend.example.com",
    });
    assert.equal(response.status, 429);
    assert.equal(response.headers.get("retry-after"), "12");
    assert.equal(response.headers.get("cache-control"), "no-store");
    const data = await response.json();
    assert.equal(data.code, "upstream_temporarily_unavailable");
    assert.equal(response.headers.get("x-statementiq-request-id"), data.request_id);
    assert.equal(originTrace, data.request_id);
    assert.notEqual(originTrace, 'untrusted-client-trace');
    assert.equal(logs[0].status, 429);
    assert.equal(logs[0].upstream_request_id, "origin-test-id");
});

test("edge proxy passes successful financial data through without modification", async t => {
    const financialData = { symbol: "AAPL", info: { price: 341.18, target_price: null } };
    t.mock.method(globalThis, "fetch", async () => Response.json(financialData));
    const response = await worker.fetch(new Request("https://statementiq-lb.com/api/analyze?ticker=AAPL"), {
        BACKEND_ORIGIN: "https://backend.example.com",
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), financialData);
});

test("edge network failures return a bounded cooldown instead of an HTML error", async t => {
    t.mock.method(console, "error", () => {});
    t.mock.method(globalThis, "fetch", async () => { throw new Error("Connection reset"); });
    const response = await worker.fetch(new Request("https://statementiq-lb.com/api/analyze?ticker=MSFT"), {
        BACKEND_ORIGIN: "https://backend.example.com",
    });
    assert.equal(response.status, 502);
    assert.equal(response.headers.get("retry-after"), "5");
    assert.equal((await response.json()).code, "upstream_temporarily_unavailable");
});

test("concurrent recovery shares one browser startup request with no cookies or referrer", async () => {
    let resolveConfig;
    const h = harness(n => n === 1 ? new Promise(resolve => { resolveConfig = resolve; })
        : new Response(null, { status: 200 }));
    const first = h.client.wakeService();
    const second = h.client.wakeService();
    assert.equal(first, second);
    assert.equal(h.calls.length, 1);
    resolveConfig(Response.json({ startup_url: "https://backend.example.com/health" }));
    await h.run(first);
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].url, "https://backend.example.com/health");
    assert.equal(h.calls[1].options.mode, "no-cors");
    assert.equal(h.calls[1].options.credentials, "omit");
    assert.equal(h.calls[1].options.referrerPolicy, "no-referrer");
    assert.equal(h.timers.size, 0);
});

test("a blocked startup probe does not prevent normal API recovery", async () => {
    const h = harness((n, options, url) => {
        if (url === "/api/startup-config") return Response.json({ startup_url: "https://backend.example.com/health" });
        if (url.startsWith("https:")) throw new TypeError("Cross-site request blocked");
        return Response.json({ symbol: "AAPL" });
    });
    await h.run(h.client.wakeService());
    const data = await h.run(h.client.requestJson("/api/analyze"));
    assert.equal(data.symbol, "AAPL");
});

test("the startup probe has its own deadline and never waits indefinitely", async () => {
    const h = harness((n, { signal }) => n === 1
        ? Response.json({ startup_url: "https://backend.example.com/health" })
        : new Promise((resolve, reject) => signal.addEventListener("abort", () => {
            reject(new DOMException("Timeout", "AbortError"));
        }, { once: true })));
    await h.run(h.client.wakeService());
    assert.equal(h.calls.length, 2);
    assert.equal(h.timers.size, 0);
});

test("startup configuration is served without contacting the sleeping backend", async t => {
    t.mock.method(globalThis, "fetch", async () => { throw new Error("Origin must not be contacted"); });
    const response = await worker.fetch(new Request("https://statementiq-lb.com/api/startup-config"), {
        BACKEND_ORIGIN: "https://backend.example.com",
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { startup_url: "https://backend.example.com/health" });
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(globalThis.fetch.mock.callCount(), 0);
});

test("startup configuration never exposes credentials or query parameters from backend configuration", async () => {
    const response = await worker.fetch(new Request("https://statementiq-lb.com/api/startup-config"), {
        BACKEND_ORIGIN: "https://user:private@backend.example.com/internal?key=private",
    });
    assert.deepEqual(await response.json(), { startup_url: "https://backend.example.com/health" });
});
