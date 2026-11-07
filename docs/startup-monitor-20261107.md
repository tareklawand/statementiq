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

Automated checks and actual cold-start verification are recorded after the
correction is published. A recovered warm endpoint alone is insufficient proof.
