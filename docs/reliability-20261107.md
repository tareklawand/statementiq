# Reliability release — 2026-11-07

## Incident evidence

GitHub runs 42348717374 and 42360392940 each failed after ten minutes with
HTTP429 on `/api/research/model-baseline?ticker=AAPL`. The old monitor retained
neither the response body machine code nor request trace headers, so these
records do not identify which upstream layer issued the limit. Do not label
these incidents as proven Yahoo, Render or Cloudflare outages.

The isolated read-only diagnosis in run 42384158488 subsequently obtained
HTTP200 for the public page, archive, proxied health, analysis, DCF baseline,
direct origin health and direct origin DCF. A recovered endpoint is not proof
that a transient restriction is permanently eliminated.

## Changes

- Temporary source failures now return retryable HTTP503, a cooldown and no-store
  headers. Unsupported security types and invalid syntax stay permanent errors.
- Source failure cooldowns begin when the failed attempt completes. Explicit
  refresh cannot repeatedly bypass a recent failure and hammer the provider.
- At most two companies download sources at once, on top of the existing
  four-statement request pool. Excess work receives retryable busy responses.
  Duplicate waiters release HTTP workers after a bounded wait and rejoin the
  existing load on retry, keeping health checks from being trapped behind many
  copies of a stalled provider request. Busy results are never financial data.
- PDF generation reuses the normal fresh source window instead of forcing a
  complete additional provider download. No financial inputs come from clients.
- DCF baseline reads use bounded startup recovery and validate issuer/shape.
- Source validation matches are cached against the actual compared numbers and
  the SEC accession, not just issuer and reporting dates. Changed rows and
  amended filings must be checked again. Unavailable checks retry after one
  minute instead of remaining cached for fifteen minutes. The cache is bounded.
- Standard HEAD health probes succeed without retrieving market data.
- Startup warming reports its actual outcome. Origin and edge share a request
  ID; error/slow-request records contain only path, status and timing. The health
  response exposes the public deployed Git revision for release verification.
- The Yahoo client is pinned to tested version 1.2.0 instead of changing silently
  on a future deployment. Other dependency updates still need regression review.
- The monitor records the exact failed stage, HTTP status, public machine code
  and trace IDs; it respects Retry-After and uses a longer cooldown on HTTP429.
  It still fails on missing statements, unavailable DCF or financial holds.
- SEC backups run independently of live analysis. Their own catalog, checksum,
  issuer, size, and isolated restoration checks remain mandatory.
- Deterministic Python regression checks run on Linux/Python 3.11 and 3.14, and
  Node 22 checks verify recovery, stale responses and the archive. Live-source
  tests are explicitly marked and remain separate from offline financial tests.
- Scheduled operational checks are separate from push-time regression checks,
  avoiding a circular deployment gate waiting on a new live release.

## Release verification

Released origin revision: `849f4e7ebf97f7b753737c02dc5d8e0a89f19fcf`.
Released Cloudflare Worker version: `6eb795e8-e7dd-41fe-8c4b-9a9568fbeb86`.
The origin's public release response header confirmed the running revision.

- Final local checks: 119 offline Python tests, 6 live-source Python tests and
  52 Node tests passed. Live tests and simulated fixtures are verification, not
  a guarantee that all providers will always be available.
- [Main regression run 42386177078](https://github.com/tareklawand/statementiq/actions/runs/42386177078)
  passed on Linux with Python 3.11, Python 3.14 and Node 22.
- Render's saved Auto-Deploy setting is **After CI Checks Pass** and its saved
  health check is `/health`. Existing free-plan billing is unchanged.
- [Post-release operations run 42386487605](https://github.com/tareklawand/statementiq/actions/runs/42386487605)
  passed both `public-service` and `public-sec-backup`. The public monitor
  completed on its first attempt with the real Apple DCF baseline ready.
- The downloaded backup artifact `public-sec-evidence-42386487605` matched its
  SHA-256 manifest. An independent restore into isolated memory passed SQLite
  integrity and verified all 9 saved public filing snapshots and their issuers.
- Production HTTP checks passed for AAPL, MSFT and nonpreset DOCU. Each returned
  all 14 core inputs. Apple DCF baseline, forecast, Excel export and PDF export
  also returned HTTP 200 from the released origin.
- A separate browser visit automatically completed Apple's analysis and loaded
  the reported DCF baseline with the forecast form available, without an error
  screen or placeholder zero values.
- A clearly labelled simulated forecast retained the prior calculation result
  for the same assumptions and passed balance-sheet and cash reconciliation.
  Its Excel export contained six valid worksheets; its PDF export was valid.
  Simulated assumptions were not installed as company actuals or saved publicly.
- Observed warm request times were 1.085 s for Apple, 4.394 s for Microsoft,
  4.386 s for DOCU and 0.686 s for Apple's DCF baseline. A repeated cached Apple
  analysis took 0.111 s. These measurements exclude a sleeping Render instance
  and are not cold-start or latency guarantees.

The final documentation-only commit uses `[skip render]` to avoid an unnecessary
second origin restart. The deployed runtime revision remains the one above.

This work does not change financial formulas, introduce sample actuals, clear
integrity holds, migrate hosting, change billing, add accounts or disable alerts.
Provider restrictions and free-host wake-up latency remain external limits.
