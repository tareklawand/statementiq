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
- PDF generation reuses the normal fresh source window instead of forcing a
  complete additional provider download. No financial inputs come from clients.
- DCF baseline reads use bounded startup recovery and validate issuer/shape.
- Source validation matches are cached against the actual compared numbers and
  the SEC accession, not just issuer and reporting dates. Changed rows and
  amended filings must be checked again. Unavailable checks retry after one
  minute instead of remaining cached for fifteen minutes. The cache is bounded.
- Standard HEAD health probes succeed without retrieving market data.
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

Before publishing: 121 Python checks passed including live sources. 51 Node
checks passed before the new baseline case; that additional case also passed.
Linux CI and production checks are verified separately after publication.

This work does not change financial formulas, introduce sample actuals, clear
integrity holds, migrate hosting, change billing, add accounts or disable alerts.
Provider restrictions and free-host wake-up latency remain external limits.
