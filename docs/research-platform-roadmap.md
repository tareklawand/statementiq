# StatementIQ research platform

This is an implementation roadmap, not a claim of institutional certification.
The public repository must remain public at the owner's request. No paid plan,
data contract or account permission may be changed without separate approval.

## Delivery gates

Release status (2026-11-05): the forecast/download/operations code is implemented
and locally verified, but is not deployed yet. GitHub rejected fast-forward main
and new-branch pushes with `remote: fatal error in commit_refs`. The live site
remains at cdba16b. Checked implementation boxes below do not mean the new release
has been published. Resume publication and live checks before marking release done.

- [x] Versioned methodology, source/input fingerprints and reproducible SEC-only snapshots.
- [x] Persistent public filing archive with checksums, migration and restore tests.
- [x] Bounded background filing-check queue, processing/retry history and explicit freshness scope.
- [x] Period-aligned financial changes and earnings-quality review with evidence.
- [x] User-selected peer comparisons with currency, fiscal-period and applicability controls.
- [x] Assumption-driven operating-company three-statement forecast and FCFF DCF, separate from actuals.
- [x] Formula-based Excel model exports with sources and reconciliation checks.
- [x] Public, account-free research notes and JSON downloads with source context.
- Accounts and team/reviewer access are excluded at the owner's explicit request (downloads only).
- [x] Archive status/error telemetry, isolated backup/restore verification and release runbook.
- [ ] Activate and verify the prepared periodic service/data checks and daily offsite backup workflow after GitHub accepts publication. Local backup and isolated restore pass.

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
  The owner currently requests no accounts, so this is outside the current scope.
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

## Forecast scope and operations

The DCF is a five-year operating-company model valued at the latest coherent
reported period, using TTM flows and a quarterly balance sheet when available. It is not a current-date quarterly stub model, bank
dividend model, REIT model, empirical credit rating or independent valuation.
Missing source inputs, minority-interest reconciliation differences, unsupported
company types and cash funding gaps are disclosed or withheld. Forecast drivers,
WACC, terminal growth/ROIC and equity-bridge choices are explicit user assumptions.
There are no default invented rates and no automatic borrowing plug.

Research notes stay in the open page and downloads. Model requests are processed
transiently for calculation/export and are not written into the public archive.
No accounts or private/team database were created.

The prepared GitHub Actions workflow checks the public service every three hours and creates a daily
checksum-verified archive backup, with a fresh isolated restore verification.
Only public SEC evidence is backed up. Artifacts retain seven days and each backup
is capped at 15 MiB before upload to bound free storage usage. A cap or failed
verification fails the job rather than publishing an incomplete backup. GitHub
schedules can be delayed/disabled after repository inactivity; these are periodic
checks and backups, not an availability or recovery-time SLA.
