/* Public research tools. Snapshot failures never replace the live analysis. */
const ResearchWorkspace = (() => {
    let data = null, sequence = 0, saved = null, peerData = null;
    const requests = new Map();
    const el = id => document.getElementById(id);
    const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    const date = value => value && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString() : "Unavailable";
    const numeric = value => typeof value === "number" && Number.isFinite(value);
    function amount(value, unit) {
        if (!numeric(value)) return "N/A";
        if (unit === "shares") return `${value.toLocaleString("en-US", {maximumFractionDigits: 0})} shares`;
        if (unit === "per_share") return value.toLocaleString("en-US", {maximumFractionDigits: 3});
        const suffix = Math.abs(value) >= 1e9 ? "B" : Math.abs(value) >= 1e6 ? "M" : "";
        const divisor = suffix === "B" ? 1e9 : suffix === "M" ? 1e6 : 1;
        return `${unit || ""} ${(value / divisor).toLocaleString("en-US", {maximumFractionDigits: 2})}${suffix}`;
    }
    function renderReview() {
        if (!data || !el("researchChanges")) return;
        const frequency = el("researchFrequency")?.value || "annual";
        const review = data.research_review || {};
        const changes = (review.changes || []).filter(c => c.frequency === frequency);
        el("researchChanges").innerHTML = changes.length ? `<div class="analysis-table-scroll research-changes-scroll"><table class="financial-table research-changes-table"><thead><tr><th>Reported line</th><th>Current period</th><th>Previous year</th><th>Change</th></tr></thead><tbody>${changes.map(c => `
            <tr><td>${escape(c.label)}<small>${escape(c.statement.replaceAll("_", " "))}</small></td>
            <td data-label="Current period">${escape(amount(c.current, c.unit))}<small>${escape(c.current_period)}</small></td>
            <td data-label="Previous year">${escape(amount(c.prior, c.unit))}<small>${escape(c.prior_period)}</small></td>
            <td data-label="Change">${numeric(c.percent_change) ? `${c.percent_change > 0 ? "+" : ""}${(c.percent_change * 100).toFixed(1)}%` : "N/M"}<small>${escape(amount(c.absolute_change, c.unit))} absolute</small></td></tr>`).join("")}</tbody></table></div>`
            : `<p class="research-note">Matching year-ago figures are unavailable for this reporting basis. No comparison has been estimated.</p>`;
        const byId = Object.fromEntries(changes.map(c => [c.id, c]));
        const signals = (review.review_signals || []).filter(s => s.frequency === frequency);
        el("researchSignals").innerHTML = signals.map(signal => `<article><h4>${escape(signal.title)}</h4><p>${escape(signal.note)}</p><dl>${signal.evidence.map(id => byId[id]).filter(Boolean).map(c => `<dt>${escape(c.label)}</dt><dd>${escape(amount(c.prior, c.unit))} to ${escape(amount(c.current, c.unit))}</dd>`).join("")}</dl></article>`).join("");
        const method = data.methodology || {};
        el("researchVersion").innerHTML = `<span>${escape(method.version || "Version unavailable")}</span><small>Methodology ${escape((method.code_sha256 || "").slice(0, 12))}</small><small>Input ${escape((data.input_sha256 || "").slice(0, 12))}</small>`;
    }
    async function loadHistory(token = sequence) {
        if (!data) return;
        const symbol = data.symbol;
        try {
            const result = await StatementIQRequests.requestJson(`/api/research/history?ticker=${encodeURIComponent(symbol)}`, {maxAttempts: 1, maxElapsedMs: 15000});
            if (token !== sequence) return;
            const snapshots = result.snapshots || [];
            if (snapshots.length) el("researchArchiveStatus").textContent = `Newest stored report period: ${snapshots[0].report_period}. Captured ${date(snapshots[0].observed_at)}.`;
            el("researchArchive").innerHTML = snapshots.length ? `<div class="analysis-table-scroll"><table class="financial-table"><thead><tr><th>Report period</th><th>Captured</th><th>Methodology</th><th>Evidence</th></tr></thead><tbody>${snapshots.map(s => `<tr><td>${escape(s.report_period)}<small>CIK ${escape(s.cik)}</small></td><td>${escape(date(s.observed_at))}</td><td>${escape(s.methodology_version)}</td><td><button class="research-button" data-snapshot-id="${escape(s.id)}">Open snapshot</button></td></tr>`).join("")}</tbody></table></div>` : `<p class="research-note">No SEC evidence has been captured for this company yet.</p>`;
            const watch = result.filing_watch;
            if (watch) el("researchArchive").innerHTML += `<p class="research-note">Last completed archive check: ${escape(date(watch.last_checked_at))}. Background checks run in a bounded queue; a 30-minute job does not guarantee each company is checked every 30 minutes.</p>`;
            const latestRun = (result.processing_history || [])[0];
            if (latestRun) el("researchArchive").innerHTML += `<p class="research-note">Last background check: ${escape(date(latestRun.finished_at || latestRun.started_at))} · ${escape(latestRun.status)}${latestRun.reason ? ` · ${escape(latestRun.reason)}` : ""}</p>`;
        } catch (error) {
            if (token === sequence) el("researchArchive").innerHTML = `<p class="research-note">The filing archive is currently unavailable. Live analysis is unchanged.</p>`;
        }
    }
    async function capture(force = false) {
        if (!data || !el("captureEvidenceBtn")) return;
        const symbol = data.symbol, token = sequence;
        const recent = requests.get(symbol);
        if (!force && recent && Date.now() - recent < 300000) return loadHistory(token);
        requests.set(symbol, Date.now());
        el("captureEvidenceBtn").disabled = true;
        el("researchArchiveStatus").textContent = "Retrieving the latest supported SEC filing evidence…";
        try {
            const result = await StatementIQRequests.requestJson(`/api/research/archive?ticker=${encodeURIComponent(symbol)}${force ? "&refresh=true" : ""}`, {maxAttempts: 2, maxElapsedMs: 120000, attemptTimeoutMs: 90000});
            if (token !== sequence) return;
            el("researchArchiveStatus").textContent = `SEC evidence for ${result.report_period} captured ${date(result.observed_at)}. Statement figures were not manually supplied.`;
            await loadHistory(token);
        } catch (error) {
            if (token !== sequence) return;
            el("researchArchiveStatus").textContent = "A complete supported SEC snapshot is currently unavailable. Live analysis is unchanged.";
            await loadHistory(token);
        } finally {
            if (token === sequence) el("captureEvidenceBtn").disabled = false;
        }
    }
    async function openSnapshot(id) {
        const token = sequence;
        el("researchFrozenEvidence").textContent = "Verifying stored evidence…";
        try {
            const result = await StatementIQRequests.requestJson(`/api/research/snapshots/${encodeURIComponent(id)}`, {maxAttempts: 1});
            if (token !== sequence) return;
            if (result.checksum_verified !== true || result.snapshot?.symbol !== data.symbol ||
                result.snapshot?.data_quality?.sec_filing?.cik !== data.data_quality?.sec_filing?.cik) throw new Error("Snapshot integrity or issuer identity failed");
            saved = result;
            const snapshot = result.snapshot;
            const raw = snapshot.metrics?.raw_financials || {};
            el("researchFrozenEvidence").innerHTML = `<div class="research-frozen"><h4>${escape(snapshot.company_name || snapshot.symbol)} · frozen evidence</h4><p>Report period ${escape(snapshot.data_quality?.sec_filing?.report_period)}. Captured ${escape(date(result.observed_at))}.</p><dl>${["revenue", "net_income", "total_assets", "operating_cash_flow"].map(key => `<dt>${escape(key.replaceAll("_", " "))}</dt><dd>${escape(amount(raw[key], snapshot.info?.currency))}</dd>`).join("")}</dl><p class="research-note">Payload checksum verified: ${escape(result.id)}. This verifies the stored payload, not an independent financial audit.</p><button class="research-button" id="downloadEvidenceBtn">Download evidence JSON</button></div>`;
        } catch (error) {
            if (token === sequence) el("researchFrozenEvidence").textContent = "The saved evidence could not be verified. It has not replaced the live analysis.";
        }
    }
    async function comparePeers(event) {
        event.preventDefault();
        if (!data) return;
        const token = sequence;
        const symbols = [...new Set([data.symbol, ...el("researchPeerTickers").value.toUpperCase().split(/[,\s]+/).filter(Boolean)])];
        if (symbols.length < 2 || symbols.length > 5 || symbols.some(symbol => !/^[A-Z0-9][A-Z0-9.\-]{0,23}$/.test(symbol))) {
            el("researchPeersStatus").textContent = "Enter one to four valid peer tickers, separated by commas.";
            return;
        }
        el("comparePeersBtn").disabled = true;
        el("researchPeersStatus").textContent = "Retrieving financial evidence and checking comparability…";
        peerData = null; el("researchPeersResult").innerHTML = "";
        try {
            const result = await StatementIQRequests.requestJson(`/api/research/peers?tickers=${encodeURIComponent(symbols.join(","))}&universe=${el("researchPeerUniverse").value}`, {maxAttempts: 1, maxElapsedMs: 120000, attemptTimeoutMs: 120000});
            if (token !== sequence) return;
            peerData = result;
            const value = (number, unit) => !numeric(number) ? "N/A" : unit === "percent" ? `${(number * 100).toFixed(2)}%` : `${number.toFixed(2)}x`;
            el("researchPeersStatus").textContent = `${result.companies.filter(company => company.included && !company.anchor).length} of ${result.companies.length - 1} peers meet the company-level filters. Individual measures may have additional exclusions.`;
            el("researchPeersResult").innerHTML = `<p class="research-note">Swipe horizontally on smaller screens to compare companies.</p><div class="analysis-table-scroll"><table class="financial-table"><thead><tr><th>Measure</th>${result.companies.map(company => `<th>${escape(company.symbol)}${company.anchor ? " · selected" : ""}</th>`).join("")}<th>Peer median</th></tr></thead><tbody>${result.measures.map(measure => `<tr><td>${escape(measure.label)}</td>${result.companies.map(company => `<td>${value(company.values[measure.key], measure.unit)}</td>`).join("")}<td>${value(measure.peer_median, measure.unit)}<small>${measure.peer_count} peers</small></td></tr>`).join("")}</tbody></table></div>
            <details class="research-peer-sources"><summary>Exclusions and source dates</summary>${result.companies.map(company => `<article><h4>${escape(company.symbol)} · ${escape(company.company_name || "Company evidence unavailable")}</h4><p>${escape(company.industry || "Industry unavailable")} · ${escape(company.currency || "Currency unavailable")} · income through ${escape(company.reporting_basis.income_period_end || "unavailable")} · balance sheet ${escape(company.reporting_basis.balance_sheet_period_end || "unavailable")}</p><p>Statements: ${escape(company.statement_source || "Unavailable")}. Quotes: ${escape(company.market_source || "Unavailable")} · ${escape(date(company.quote_as_of))}.</p>${company.exclusions.length ? `<p>${escape(company.exclusions.join("; "))}</p>` : `<p>Company-level filters passed.</p><ul>${result.measures.filter(measure => company.unavailable[measure.key]).map(measure => `<li>${escape(measure.label)}: ${escape(company.unavailable[measure.key])}</li>`).join("")}</ul>`}</article>`).join("")}</details><button class="research-button" id="downloadPeersBtn">Download comparison JSON</button>`;
        } catch (error) {
            if (token === sequence) el("researchPeersStatus").textContent = "Peer evidence could not be retrieved. No comparison has been estimated. Try again shortly.";
        } finally {
            if (token === sequence) el("comparePeersBtn").disabled = false;
        }
    }
    function downloadJSON(payload, filename) {
        const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"}));
        const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
    document.addEventListener("submit", event => { if (event.target.id === "researchPeersForm") void comparePeers(event); });
    document.addEventListener("change", event => { if (event.target.id === "researchFrequency") renderReview(); });
    document.addEventListener("click", event => {
        const target = event.target.closest("button");
        if (!target) return;
        if (target.id === "captureEvidenceBtn") void capture(true);
        if (target.dataset.snapshotId) void openSnapshot(target.dataset.snapshotId);
        if (target.id === "downloadEvidenceBtn" && saved) {
            downloadJSON(saved, `${data.symbol}_SEC_evidence_${saved.id.slice(0, 12)}.json`);
        }
        if (target.id === "downloadPeersBtn" && peerData) downloadJSON(peerData, `${data.symbol}_peer_comparison.json`);
    });
    return {setData(payload) {
        data = payload; sequence += 1; saved = null; peerData = null;
        if (!el("researchChanges")) return;
        el("researchFrozenEvidence").innerHTML = "";
        el("researchArchive").innerHTML = "";
        el("captureEvidenceBtn").disabled = false;
        el("comparePeersBtn").disabled = false;
        el("researchPeersStatus").textContent = ""; el("researchPeersResult").innerHTML = "";
        el("researchArchiveStatus").textContent = "Loading SEC evidence history…";
        renderReview();
        if (data.data_quality?.sec_filing?.status === "verified") void capture();
        else { el("researchArchiveStatus").textContent = "No verified SEC registrant is available for this company."; el("captureEvidenceBtn").disabled = true; }
    }};
})();
