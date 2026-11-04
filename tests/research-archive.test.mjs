import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {DatabaseSync} from "node:sqlite";
import {captureLatest, handleResearchArchive, normalizedEvidence, scheduledFilingChecks, sha256, stableJson, storeSnapshot} from "../src/research-archive.js";

function database() {
    const sqlite = new DatabaseSync(":memory:");
    sqlite.exec(readFileSync(new URL("../migrations/0001_research_archive.sql", import.meta.url), "utf8"));
    const db = {
        sqlite,
        prepare(sql) {
            const statement = sqlite.prepare(sql);
            const wrap = parameters => ({
                bind(...values) { return wrap(Object.fromEntries(values.map((value, i) => [`?${i + 1}`, value]))); },
                async first() { return statement.get(parameters) || null; },
                async all() { return {results: statement.all(parameters)}; },
                async run() { return statement.run(parameters); },
            });
            return wrap({});
        },
        async batch(statements) {
            sqlite.exec("BEGIN");
            try {
                const results = [];
                for (const statement of statements) results.push(await statement.run());
                sqlite.exec("COMMIT");
                return results;
            } catch (error) { sqlite.exec("ROLLBACK"); throw error; }
        },
    };
    return db;
}

function evidence(accession="test-annual") {
    return {symbol: "EXAMPLE", purpose: "public_sec_filing_evidence", info: {price: null, market_cap: null},
        metrics: {valuation_score: null, health_score: 70}, methodology: {version: "test-1", code_sha256: "a".repeat(64)},
        data_quality: {statement_provider: "SEC Company Facts", fetched_at: "2026-01-01T00:00:00Z",
            analysis_basis: {statement_age_days: 5}, sec_filing: {status: "verified", cik: "0000123456", accession_number: accession, report_period: "2025-12-31"}}};
}

test("snapshots are deduplicated independent of fetch time and preserve first observation", async () => {
    const db = database();
    const first = await storeSnapshot(db, evidence(), "EXAMPLE", "2026-01-01T00:00:00Z");
    const updated = evidence();
    updated.data_quality.fetched_at = "2026-01-02T00:00:00Z";
    updated.data_quality.analysis_basis.statement_age_days = 6;
    const second = await storeSnapshot(db, updated, "EXAMPLE", "2026-01-02T00:00:00Z");
    assert.equal(first.id, second.id);
    assert.equal(second.observed_at, first.observed_at);
    assert.equal(db.sqlite.prepare("SELECT COUNT(*) AS n FROM filing_snapshots").get().n, 1);
    assert.ok(updated.data_quality.fetched_at); // normalization does not mutate the caller
});

test("the archive refuses client-style, wrong-issuer and market-provider payloads", () => {
    const data = evidence();
    assert.throws(() => normalizedEvidence({...data, symbol: "OTHER"}, "EXAMPLE"));
    assert.throws(() => normalizedEvidence({...data, info: {price: 123}}, "EXAMPLE"));
    assert.throws(() => normalizedEvidence({...data, purpose: "analysis"}, "EXAMPLE"));
    data.data_quality.statement_provider = "Yahoo Finance";
    assert.throws(() => normalizedEvidence(data, "EXAMPLE"));
});

test("SQL enforces append-only snapshots and checksum verification detects an administrator edit", async () => {
    const db = database();
    const saved = await storeSnapshot(db, evidence(), "EXAMPLE");
    assert.throws(() => db.sqlite.exec("UPDATE filing_snapshots SET payload='{}'"), /append-only/);
    assert.throws(() => db.sqlite.exec("DELETE FROM filing_snapshots"), /append-only/);
    let result = await handleResearchArchive(new Request(`https://example.com/api/research/snapshots/${saved.id}`), {RESEARCH_DB: db});
    assert.equal((await result.json()).checksum_verified, true);
    db.sqlite.exec("DROP TRIGGER snapshots_no_update"); // isolated test DB only
    db.sqlite.exec("UPDATE filing_snapshots SET payload='{}'");
    result = await handleResearchArchive(new Request(`https://example.com/api/research/snapshots/${saved.id}`), {RESEARCH_DB: db});
    assert.equal(result.status, 503);
});

test("new accessions are additional records, not overwrites", async () => {
    const db = database();
    const original = await storeSnapshot(db, evidence(), "EXAMPLE");
    const amended = await storeSnapshot(db, evidence("amended"), "EXAMPLE");
    assert.notEqual(original.id, amended.id);
    const result = await handleResearchArchive(new Request("https://example.com/api/research/history?ticker=EXAMPLE"), {RESEARCH_DB: db});
    assert.equal((await result.json()).snapshots.length, 2);
});

test("public archive does not accept financial writes or malformed identifiers", async () => {
    const env = {RESEARCH_DB: database()};
    assert.equal((await handleResearchArchive(new Request("https://example.com/api/research/archive", {method: "POST", body: "{}"}), env)).status, 405);
    assert.equal((await handleResearchArchive(new Request("https://example.com/api/research/history?ticker=%27%20OR%201%3D1"), env)).status, 400);
    assert.equal((await handleResearchArchive(new Request("https://example.com/api/research/snapshots/not-a-hash"), env)).status, 400);
    assert.equal((await handleResearchArchive(new Request("https://example.com/api/research/status"), {})).status, 503);
});

test("snapshot storage failures stay isolated as a retryable JSON response", async () => {
    const db = {prepare() { return {bind() { return {async first() { throw new Error("Simulated database unavailability"); }}; }}; }};
    const result = await handleResearchArchive(new Request(`https://example.com/api/research/snapshots/${"a".repeat(64)}`), {RESEARCH_DB: db});
    assert.equal(result.status, 503);
    assert.equal((await result.json()).status, "unavailable");
});

test("scheduled checks do not wake the analysis server for unchanged filings", async () => {
    const db = database();
    await storeSnapshot(db, evidence(), "EXAMPLE", "2020-01-01T00:00:00Z");
    const urls = [];
    await scheduledFilingChecks({RESEARCH_DB: db, BACKEND_ORIGIN: "https://backend.example"}, async url => {
        urls.push(String(url));
        return Response.json({cik: 123456, filings: {recent: {
            form: ["10-K"], reportDate: ["2025-12-31"], filingDate: ["2026-02-01"], accessionNumber: ["test-annual"]
        }}});
    });
    assert.equal(urls.length, 1);
    assert.ok(urls[0].startsWith("https://data.sec.gov/"));
    assert.equal(db.sqlite.prepare("SELECT status FROM ingestion_runs").get().status, "unchanged");
});

test("a newly reported filing is captured by the bounded scheduled importer", async () => {
    const db = database();
    await storeSnapshot(db, evidence(), "EXAMPLE", "2020-01-01T00:00:00Z");
    await scheduledFilingChecks({RESEARCH_DB: db, BACKEND_ORIGIN: "https://backend.example"}, async url => {
        if (String(url).startsWith("https://data.sec.gov/")) return Response.json({cik: 123456, filings: {recent: {
            form: ["10-K/A"], reportDate: ["2025-12-31"], filingDate: ["2026-02-02"], accessionNumber: ["amended"]
        }}});
        return Response.json(evidence("amended"));
    });
    assert.equal(db.sqlite.prepare("SELECT COUNT(*) AS n FROM filing_snapshots").get().n, 2);
    assert.equal(db.sqlite.prepare("SELECT status FROM ingestion_runs").get().status, "archived");
});

test("canonical evidence order is deterministic and does not admit non-finite numbers", () => {
    assert.equal(stableJson({b: 2, a: [1, null]}), stableJson({a: [1, null], b: 2}));
    assert.throws(() => stableJson({value: NaN}));
});

test("archive cooldown uses the latest retrieval time without rewriting the original observation", async () => {
    const db = database();
    const original = await storeSnapshot(db, evidence(), "EXAMPLE", "2020-01-01T00:00:00Z");
    await storeSnapshot(db, evidence(), "EXAMPLE");
    const response = await handleResearchArchive(new Request("https://example.com/api/research/archive?ticker=EXAMPLE"), {RESEARCH_DB: db});
    const result = await response.json();
    assert.equal(response.status, 200);
    assert.equal(result.cached, true);
    assert.equal(result.observed_at, original.observed_at);
    assert.equal(result.id, original.id);
});

test("canonical server evidence is stored byte-for-byte and verifies on retrieval", async () => {
    const db = database();
    const body = JSON.stringify(normalizedEvidence(evidence(), "EXAMPLE"));
    const captured = await captureLatest({RESEARCH_DB: db, BACKEND_ORIGIN: "https://backend.example"}, "EXAMPLE", async () => new Response(body));
    assert.equal(captured.id, await sha256(body));
    assert.equal(db.sqlite.prepare("SELECT payload FROM filing_snapshots").get().payload, body);
    const result = await handleResearchArchive(new Request(`https://example.com/api/research/snapshots/${captured.id}`), {RESEARCH_DB: db});
    assert.equal((await result.json()).checksum_verified, true);
});

test("scheduled checks ignore future filings and retry numeric indexing lag", async () => {
    const db = database();
    await storeSnapshot(db, evidence(), "EXAMPLE", "2020-01-01T00:00:00Z");
    await scheduledFilingChecks({RESEARCH_DB: db, BACKEND_ORIGIN: "https://backend.example"}, async url => {
        if (String(url).startsWith("https://data.sec.gov/")) return Response.json({cik: 123456, filings: {recent: {
            form: ["10-K", "10-K/A"], reportDate: ["2099-12-31", "2025-12-31"],
            filingDate: ["2100-02-01", "2026-02-02"], accessionNumber: ["future", "amended"]
        }}});
        return Response.json(evidence()); // newest submission is not yet indexed
    });
    const run = db.sqlite.prepare("SELECT status,reason FROM ingestion_runs").get();
    assert.equal(run.status, "unavailable");
    assert.match(run.reason, /not yet indexed/);
    assert.equal(db.sqlite.prepare("SELECT accession FROM filing_watch").get().accession, "test-annual");
});
