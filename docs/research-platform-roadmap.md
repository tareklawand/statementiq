# StatementIQ research platform

This is an implementation roadmap, not a claim of institutional certification.
The public repository must remain public at the owner's request. No paid plan,
data contract or account permission may be changed without separate approval.

## Delivery gates

- [x] Versioned methodology, source/input fingerprints and reproducible SEC-only snapshots.
- [x] Persistent public filing archive with checksums, migration and restore tests.
- [x] Bounded background filing-check queue, processing/retry history and explicit freshness scope.
- [x] Period-aligned financial changes and earnings-quality review with evidence.
- [x] User-selected peer comparisons with currency, fiscal-period and applicability controls.
- [ ] Assumption-driven three-statement and cash-flow valuation models, separate from actuals.
- [ ] Formula-based Excel exports, including sources and reconciliation checks.
- [ ] Saved research and annotations, with clearly stated storage and privacy boundaries.
- [ ] Authenticated team/reviewer workflow and access-control tests.
- [x] Archive status/error telemetry, isolated backup/restore verification and release runbook.
- [ ] Continuous production monitoring and recurring offsite backup/restore drills.

The archive was deployed and exercised with AAPL and a non-preset ticker, DOCU.
A production SQL export restored into isolated SQLite with both payload checksums
and issuer metadata verified. The background queue is configured on Cloudflare;
its tests cover unchanged filings, new accessions and numerical-indexing delay.
An installed schedule is not a per-issuer update-time or uptime guarantee.

## External prerequisites

- Institutional market-data use requires appropriate provider rights. The current
  Yahoo route does not itself establish commercial redistribution permission.
- Paid always-on infrastructure is not authorized. A free-tier deployment cannot
  be described as an enterprise availability commitment.
- Team identity/SSO, administrator ownership and membership policies need an
  operator-approved identity configuration before private server workspaces run.
- Independent accounting, model and security reviews cannot be self-certified by
  software tests. Customer pilots and procurement review require real participants.

## Data policy

The public archive stores SEC-derived statement evidence, not market quotes,
private portfolios, individual search logs or confidential user documents.
Historical snapshots mean "observed and stored at this time". They do not
reconstruct information that was never captured or eliminate look-ahead bias in
older vendor-standardized historical data. A checksum detects payload changes;
it is not proof against an administrator rewriting an entire database.

Forecast assumptions and analyst adjustments must never overwrite actuals or
silently affect the public financial-health screen. Missing inputs are not zero.
