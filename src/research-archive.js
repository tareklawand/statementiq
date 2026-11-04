// Public filing evidence only. No client-provided financial payload is saved.
const SYMBOL = /^[A-Z0-9][A-Z0-9.\-]{0,23}$/;
const SNAPSHOT = /^[a-f0-9]{64}$/;
const MAX_BYTES = 1_000_000;

export function stableJson(value) {
  if (value === null || typeof value !== "object") {
    if (typeof value === "number" && !Number.isFinite(value)) throw new Error("Non-finite evidence");
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  return `{${Object.keys(value).sort().filter(k => value[k] !== undefined)
    .map(key => `${JSON.stringify(key)}:${stableJson(value[key])}`).join(",")}}`;
}

export async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2, "0")).join("");
}

function validateEvidence(payload, symbol) {
  const quality = payload.data_quality || {};
  const filing = quality.sec_filing || {};
  if (payload.purpose !== "public_sec_filing_evidence" || payload.symbol !== symbol ||
      quality.statement_provider !== "SEC Company Facts" || filing.status !== "verified" ||
      !/^\d{10}$/.test(filing.cik || "") || !filing.accession_number || !filing.report_period ||
      !SNAPSHOT.test(payload.methodology?.code_sha256 || "") ||
      payload.info?.price != null || payload.info?.market_cap != null ||
      payload.info?.target_price != null || payload.metrics?.valuation_score != null) {
    throw new Error("Response is not a verified SEC-only evidence snapshot");
  }
}

export function normalizedEvidence(payload, symbol) {
  validateEvidence(payload, symbol);
  const copy = JSON.parse(JSON.stringify(payload));
  delete copy.data_quality.fetched_at;
  for (const key of Object.keys(copy.data_quality.analysis_basis || {})) {
    if (key.endsWith("age_days")) delete copy.data_quality.analysis_basis[key];
  }
  return copy;
}

function json(value, status = 200) {
  return Response.json(value, {status, headers: {"cache-control": "no-store"}});
}

function ticker(url) {
  const value = String(url.searchParams.get("ticker") || "").trim().toUpperCase();
  if (!SYMBOL.test(value)) throw new Error("Enter a valid company ticker");
  return value;
}

export async function storeSnapshot(db, payload, symbol, observedAt = new Date().toISOString()) {
  const evidence = normalizedEvidence(payload, symbol);
  const body = stableJson(evidence);
  return writeSnapshot(db, evidence, body, symbol, observedAt);
}

async function writeSnapshot(db, evidence, body, symbol, observedAt) {
  if (new TextEncoder().encode(body).length > MAX_BYTES) throw new Error("Evidence exceeds archive size limit");
  const id = await sha256(body);
  const filing = evidence.data_quality.sec_filing;
  await db.batch([
    db.prepare(`INSERT INTO filing_snapshots(id, symbol, cik, accession, report_period, observed_at,
      methodology_version, methodology_sha256, payload) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)
      ON CONFLICT(id) DO NOTHING`).bind(id, symbol, filing.cik, filing.accession_number, filing.report_period,
        observedAt, evidence.methodology.version, evidence.methodology.code_sha256, body),
    db.prepare(`INSERT INTO filing_watch(symbol,cik,accession,report_period,last_checked_at,last_requested_at)
      VALUES(?1,?2,?3,?4,?5,?5) ON CONFLICT(symbol) DO UPDATE SET
      cik=excluded.cik,accession=excluded.accession, report_period=excluded.report_period,
      last_checked_at=excluded.last_checked_at,last_requested_at=excluded.last_requested_at`)
      .bind(symbol, filing.cik, filing.accession_number, filing.report_period, observedAt),
  ]);
  const stored = await db.prepare("SELECT observed_at FROM filing_snapshots WHERE id=?1").bind(id).first();
  return {id, observed_at: stored.observed_at, report_period: filing.report_period,
    accession: filing.accession_number, checksum_sha256: id, status: "archived"};
}

async function readSnapshot(db, id) {
  const record = await db.prepare("SELECT * FROM filing_snapshots WHERE id=?1").bind(id).first();
  if (!record) return json({detail: "Snapshot not found"}, 404);
  if (await sha256(record.payload) !== record.id) {
    console.error(JSON.stringify({event: "snapshot_checksum_failure", snapshot: id}));
    return json({detail: "Snapshot checksum failed. The stored evidence is unavailable for use."}, 503);
  }
  return json({id, observed_at: record.observed_at, checksum_verified: true,
    snapshot: JSON.parse(record.payload), historical_scope: "Captured observation only; not a reconstruction of knowledge before capture."});
}

export async function captureLatest(env, symbol, fetcher = fetch) {
  const source = new URL("/api/research/filing-snapshot", env.BACKEND_ORIGIN);
  source.searchParams.set("ticker", symbol);
  const response = await fetcher(source, {headers: {"accept": "application/json"}, signal: AbortSignal.timeout(90000)});
  if (!response.ok) throw new Error(`SEC evidence source unavailable (HTTP ${response.status})`);
  const content = await response.text();
  if (new TextEncoder().encode(content).length > MAX_BYTES) throw new Error("Evidence exceeds archive size limit");
  const evidence = JSON.parse(content);
  validateEvidence(evidence, symbol);
  // Current Python source emits canonical JSON with volatile retrieval ages
  // removed. Hash/store those exact bytes instead of recursively reserializing
  // hundreds of KB of provenance inside a free-plan Worker.
  if (!Object.hasOwn(evidence.data_quality, "fetched_at") &&
      !Object.keys(evidence.data_quality.analysis_basis || {}).some(key => key.endsWith("age_days"))) {
    return writeSnapshot(env.RESEARCH_DB, evidence, content, symbol, new Date().toISOString());
  }
  return storeSnapshot(env.RESEARCH_DB, evidence, symbol);
}

export async function handleResearchArchive(request, env) {
  const url = new URL(request.url);
  const path = url.pathname;
  if (!["/api/research/archive", "/api/research/history", "/api/research/status"].includes(path) &&
      !path.startsWith("/api/research/snapshots/")) return null;
  if (request.method !== "GET") return json({detail: "Only read requests are supported"}, 405);
  if (!env.RESEARCH_DB) return json({status: "not_configured", detail: "Persistent filing history is not configured."}, 503);
  try {
    if (path === "/api/research/status") {
      await env.RESEARCH_DB.prepare("SELECT id FROM filing_snapshots LIMIT 1").first();
      return json({status: "ready", scope: "Public SEC filing evidence only", scheduled_job_minutes: 30,
        max_checks_per_job: 3, max_imports_per_job: 1,
        freshness_scope: "Bounded queue for successfully archived issuers; not a per-company freshness guarantee. On-demand analysis also checks filing freshness.",
        point_in_time_scope: "Observations collected since archive activation; no pre-capture historical claim."});
    }
    if (path.startsWith("/api/research/snapshots/")) {
      const id = path.split("/").pop();
      return SNAPSHOT.test(id) ? readSnapshot(env.RESEARCH_DB, id) : json({detail: "Invalid snapshot identifier"}, 400);
    }
    let symbol;
    try { symbol = ticker(url); } catch (error) { return json({detail: error.message}, 400); }
    if (path === "/api/research/history") {
      const records = await env.RESEARCH_DB.prepare(`SELECT id, cik, accession, report_period, observed_at,
        methodology_version, methodology_sha256 FROM filing_snapshots WHERE symbol=?1
        ORDER BY observed_at DESC, id DESC LIMIT 30`).bind(symbol).all();
      const runs = await env.RESEARCH_DB.prepare(`SELECT started_at,finished_at,status,snapshot_id,reason
        FROM ingestion_runs WHERE symbol=?1 ORDER BY started_at DESC LIMIT 10`).bind(symbol).all();
      const watch = await env.RESEARCH_DB.prepare(`SELECT cik,accession,report_period,last_checked_at,last_requested_at
        FROM filing_watch WHERE symbol=?1`).bind(symbol).first();
      return json({symbol, snapshots: records.results || [], processing_history: runs.results || [], filing_watch: watch,
        scope: "Captured SEC evidence only. Earlier market data and private research are not stored."});
    }
    const recent = await env.RESEARCH_DB.prepare(`SELECT id,observed_at,report_period,accession FROM filing_snapshots
      WHERE symbol=?1 ORDER BY observed_at DESC LIMIT 1`).bind(symbol).first();
    const watch = await env.RESEARCH_DB.prepare("SELECT last_requested_at FROM filing_watch WHERE symbol=?1").bind(symbol).first();
    const cooldown = url.searchParams.get("refresh") === "true" ? 30000 : 300000;
    if (recent && watch && Date.now() - Date.parse(watch.last_requested_at) < cooldown) {
      return json({...recent, status: "archived", checksum_sha256: recent.id, last_requested_at: watch.last_requested_at, cached: true});
    }
    const result = await captureLatest(env, symbol);
    return json(result);
  } catch (error) {
    console.error(JSON.stringify({event: "research_archive_error", path, message: error.message}));
    return json({status: "unavailable", detail: "Filing history is temporarily unavailable. The current analysis has not been changed."}, 503);
  }
}

export async function scheduledFilingChecks(env, fetcher = fetch) {
  if (!env.RESEARCH_DB) return;
  const due = await env.RESEARCH_DB.prepare(`SELECT * FROM filing_watch WHERE last_checked_at < ?1
    ORDER BY last_checked_at ASC LIMIT 3`).bind(new Date(Date.now() - 25 * 60000).toISOString()).all();
  for (const watch of due.results || []) {
    await new Promise(resolve => setTimeout(resolve, 300));
    const runId = crypto.randomUUID();
    const now = new Date().toISOString();
    await env.RESEARCH_DB.prepare("INSERT INTO ingestion_runs(id,symbol,started_at,status) VALUES(?1,?2,?3,'running')")
      .bind(runId, watch.symbol, now).run();
    let status = "unavailable", snapshotId = null, reason = null, attemptedImport = false;
    try {
      if (!/^\d{10}$/.test(watch.cik)) throw new Error("Invalid SEC registrant identifier");
      const response = await fetcher(`https://data.sec.gov/submissions/CIK${watch.cik}.json`, {
        headers: {"user-agent": "StatementIQ/1.0 statementiq-lb.com", "accept": "application/json"},
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error(`SEC filing check unavailable (HTTP ${response.status})`);
      const payload = await response.json();
      if (String(payload.cik).padStart(10, "0") !== watch.cik) throw new Error("SEC registrant mismatch");
      const recent = payload.filings?.recent || {};
      const forms = new Set(["10-K", "10-Q", "10-K/A", "10-Q/A", "20-F", "20-F/A", "40-F", "40-F/A"]);
      const today = now.slice(0, 10);
      const validDate = value => /^\d{4}-\d{2}-\d{2}$/.test(value || "") && Number.isFinite(Date.parse(value)) && value <= today;
      const positions = (recent.form || []).map((form, i) => i).filter(i => forms.has(recent.form[i]) &&
        validDate(recent.reportDate?.[i]) && validDate(recent.filingDate?.[i]) && recent.accessionNumber?.[i]);
      positions.sort((a,b) => `${recent.reportDate[b]}:${recent.filingDate[b]}`.localeCompare(`${recent.reportDate[a]}:${recent.filingDate[a]}`));
      if (!positions.length) throw new Error("No periodic SEC filing found");
      const latest = positions[0];
      if (recent.accessionNumber[latest] === watch.accession) status = "unchanged";
      else {
        attemptedImport = true;
        const saved = await captureLatest(env, watch.symbol, fetcher);
        // SEC metadata can precede numeric indexing. Keep retrying on the next
        // scheduled run rather than marking the older filing as updated.
        if (saved.accession !== recent.accessionNumber[latest]) throw new Error("Newest filing is not yet indexed for complete import");
        snapshotId = saved.id;
        status = "archived";
      }
    } catch (error) { reason = error.message; }
    await env.RESEARCH_DB.batch([
      env.RESEARCH_DB.prepare("UPDATE ingestion_runs SET finished_at=?1,status=?2,snapshot_id=?3,reason=?4 WHERE id=?5")
        .bind(new Date().toISOString(), status, snapshotId, reason, runId),
      env.RESEARCH_DB.prepare("UPDATE filing_watch SET last_checked_at=?1 WHERE symbol=?2").bind(now, watch.symbol),
    ]);
    // Keep the free-tier job bounded. Remaining issuers stay due for the next
    // run; the UI reports the last completed check rather than promising an SLA.
    if (attemptedImport) break;
  }
}
