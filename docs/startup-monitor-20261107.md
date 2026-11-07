# Follow-up alert — 2026-11-07

## Failure and diagnosis

[Scheduled run 42396050456](https://github.com/tareklawand/statementiq/actions/runs/42396050456)
failed from 17:23 to 17:32 UTC after ten HTTP 429 responses at the
`company_analysis` stage. Each response had the Worker's
`upstream_temporarily_unavailable` code, not an application financial hold.
The independently scheduled backup was not due at that hour and was skipped
by its existing schedule; it did not fail.

At about 18:40 UTC, the public page and D1 archive were available, but even
proxied `/health` returned 429. Direct Render `/health` initially returned 503.
Render logs then showed a new server start at 18:41:26 UTC and application
readiness at 18:41:45 UTC. The default financial source warmup completed at
18:41:49 UTC. The direct health request started the sleeping service; subsequent
proxied health, Apple analysis and DCF baseline all returned 200.

The scheduled monitor omitted the direct startup-health request already used
by browser visits. Repeated requests through the Worker did not reliably wake
the free instance. The earlier post-release check ran against an awake origin
and did not exercise this gap. This incident did not originate in a financial
formula, missing filing or a proved Yahoo restriction.

## Correction

- Read the existing public `/api/startup-config` and validate its exact service
  health URL before using it. No credentials are sent to the wake-up endpoint.
- Contact Render's `/health` directly within the existing recovery budget.
  HTTP 503/429 cooldowns remain respected while startup completes.
- Require the expected healthy service response, then still require successful
  public analysis with real positive core inputs, no financial integrity hold,
  and a ready DCF baseline. Waking alone cannot make a check pass.
- Preserve alerts if the origin or any actual analysis check remains unavailable.
  Keep the three-hour schedule, daily verified backups, free plans and financial
  calculation code unchanged. This is a monitoring-only release; `[skip render]`
  avoids an unnecessary application restart.

## Verification

- Correction revision: `ff877417f7b0eccfccb21b62983f8e73cca10871`.
- All 127 offline Python checks passed locally. The merged original project
  also passed its 21 focused monitoring/recovery checks, preserving existing
  unpublished sector-classification work.
- [Linux regression run 42402949791](https://github.com/tareklawand/statementiq/actions/runs/42402949791)
  passed on Python 3.11 and 3.14; all 52 Node checks passed too.
- After more than 15 minutes without analysis/origin requests, a single public
  `/health` check at 18:58:34 UTC reproduced HTTP429 with no application release
  header, trace `cf5bd605-0321-4c61-8665-e00816a43889`.
- [Cold-start operations run 42403931098](https://github.com/tareklawand/statementiq/actions/runs/42403931098)
  started its monitor at 18:58:55 UTC. Its direct `origin_health` stage returned
  startup HTTP503 on attempts 1–4. It respected cooldowns and completed both
  real analysis and DCF checks on attempt 5 at 19:00:05 UTC: approximately
  **70 seconds from monitor start**. No manual restart or concurrent manual
  origin wake-up was used during this test. This is one observed cold start,
  not a latency guarantee.
- Both availability and independent public-backup jobs completed successfully.
  The new backup artifact is `public-sec-evidence-42403931098`. Its downloaded
  archive matched the SHA-256 manifest, and an independent isolated restoration
  verified all 10 snapshots and passed SQLite integrity checks.

The earlier warm-only success did not verify this case. Future availability
checks now exercise the direct wake-up path and still alert if real analysis
cannot complete within their bounded recovery budget.
