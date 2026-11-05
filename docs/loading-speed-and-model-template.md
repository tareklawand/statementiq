# Analysis loading and DCF template — 2026-11-05

## What changed

Normal searches, Enter submissions and preset ticker clicks no longer force a
complete source reload when the existing five-minute analysis window is valid.
The explicit Refresh data button still bypasses that window. Source retrieval
times remain visible. Quote timestamps are never replaced with retrieval times.

Concurrent loads for the same company share one source request, including startup
warming and the first visitor. Independent provider statement reads use separate
ticker instances in a process-wide pool of at most four workers. Complete primary
quotes no longer trigger unnecessary fallback downloads. Missing primary fields
retain the live fallback routes and missing-data safeguards.

The dashboard no longer waits for annual-report text extraction. The separate
topic-locator request runs when Financial statements is opened and only applies
to the same company, analysis object and annual filing URL. Numerical statement,
recency and reconciliation checks still run before analysis is returned.

Every stock-cache miss checks SEC submissions freshly, avoiding a second metadata
cache window hiding a newly filed report. The DCF reuses recent SEC checks and
already imported SEC statement frames. Input fingerprints still reject a changed
baseline before calculation or Excel export.

Cloudflare can serve public GET analyses within their original source deadline.
It does not add another five-minute lifetime. It excludes forecast/export POSTs,
API keys, authorization headers, unknown query parameters, errors, non-JSON
responses and invalid/missing deadlines. Worker version metadata separates caches
across releases. A cache outage falls through to the source. No persistent market
history, private models, notes or new accounts are introduced.

Server-Timing separates source loading from calculation time for diagnosis.
The existing free Render service can still sleep after inactivity. These changes
remove avoidable work and repeated loads, not the hosting provider's cold start.

## DCF presentation

The web template groups operating, working-capital and financing drivers, with
discount-rate and equity-bridge inputs beside them. The result puts per-share,
enterprise and equity values together, then shows the enterprise-to-equity bridge
and terminal assumptions. It retains the linked statements, scope and source data.
Phone and tablet layouts reflow without document-wide horizontal overflow.

Excel exports keep the same six sheets and calculation references. The main
valuation view now includes an explicit bridge and linked valuation assumptions.
Reported and forecast columns are labelled, subtotals are emphasized and working
schedules are grouped. Source actuals and every existing model formula remain
separate from editable assumptions. No assumptions or financial values are supplied
by the visual redesign.

## Verification

Before changes, live warm Apple analysis took 5.03 seconds and the next request
0.84 seconds in one measured sequence. Those are observations, not an idle-start
benchmark or a latency guarantee. Local cache reads subsequently took 0.004–0.020
seconds, DCF calculation 0.062 seconds and export 0.555 seconds in a warm preview.
Production measurements must be recorded separately after release.

The full financial suite and browser/server state checks cover source equality,
concurrent-load deduplication, deferred report review, normal versus forced
refresh, cache deadlines, release isolation and private-input exclusion. The
spreadsheet engine independently recalculates all projected lines and valuations,
including edited and missing inputs, and renders the revised template. The same
labelled simulated case remains USD110.880502299 per share at its baseline date.
This software verification is not an independent accounting or valuation review.
