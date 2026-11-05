# Public research archive operations

Owner: StatementIQ operator. This archive holds public SEC evidence only.
It is not a private team workspace, market-data history product or independently
validated institutional service. Keep the GitHub repository public at the
owner's current instruction. No paid upgrade has been approved.

## Release checks

1. Run Python `pytest -q tests` and Node `node --test tests/*.test.mjs`.
2. Apply schema migrations to local D1 first. Production migrations must preserve
   existing records; the initial migration only creates new archive tables.
3. Deploy the source API before the edge/UI release. Confirm the SEC-only endpoint
   returns actual source figures, no quote/valuation values, and a source revision.
4. Capture one supported public issuer through the edge API. Read the stored ID,
   open its snapshot, and confirm the payload checksum. Capture again to verify
   deduplication and the original observation time. Test a ticker outside presets.
5. Check the new research tab on desktop, tablet and phone; confirm failed archive
   calls do not hide or overwrite a completed live analysis.
6. Inspect background processing history after a scheduled job. A running job is
   not a successful update. A new accession that is not numerically indexed must
   remain pending/unavailable and be retried. The free queue handles up to three
   checks and one full import per 30-minute invocation, not all issuers each run.

## Backup and isolated restore verification

Cloudflare's production D1 databases have automatic Time Travel. The free plan
retains a seven-day window. See the provider's current documentation:
https://developers.cloudflare.com/d1/reference/time-travel/

For an independent readable export, from the repository directory run:

```
npx wrangler d1 export statementiq-research --remote --output /absolute/path/archive.sql
python3 scripts/verify_archive_backup.py /absolute/path/archive.sql
```

The verifier restores the SQL into a fresh in-memory SQLite database, runs its
integrity check and compares every saved payload's checksum and issuer metadata.
It never restores over production. Keep exports in operator-controlled storage.
Production Time Travel restoration is a separate operator action: it can roll
back newer records and must not be used as a routine test.

The active research-operations GitHub Actions workflow checks service/data every
three hours and backs up the public evidence archive daily at 01:00 UTC. It uses
the catalog's fixed observation cutoff and exact canonical snapshot bytes,
verifies every checksum, and restores immutable records in isolated SQLite before
uploading the artifact. Backups retain seven days and have a 15 MiB compressed
size cap. Download artifacts from the repository's Actions page. This public
backup excludes mutable processing logs, private forecasts and notes; use an
operator SQL export for operational tables. Failures are visible in Actions and
the owner's existing GitHub notification settings. Scheduled jobs can be delayed
or disabled after repository inactivity. No recovery-time or uptime SLA is promised.
The first service-check and backup jobs succeeded on 2026-11-05. The retained
artifact and production restore verification are recorded in
`docs/release-verification-20261105.md`.

## Failure handling and capacity

- `/api/research/status` confirms the binding/schema is accessible.
- `/api/research/history?ticker=SYMBOL` includes capture dates, the actual last
  check and processing outcomes. `/api/research/snapshots/ID` verifies its payload.
- Checksums cover exact frozen payload bytes, not capture-time authenticity or
  protection against a database administrator rewriting schema and records.
- The analysis server performs canonical serialization; the free Worker hashes
  and stores its bytes. Limit provenance payloads to 1 MB and imports to one/job.
- In the Cloudflare dashboard inspect invocation errors, CPU time, D1 storage,
  rows read and rows written. Free quotas can halt requests until reset or
  capacity is made available. They are not an uptime guarantee.
- Archive errors are separate from live analysis and never substitute zeros or
  manually provided numbers. Do not clear a financial-integrity hold to restore
  a headline score. Record the actual provider/SEC error before retrying.
- For a failing release, roll back the Worker/source code to the preceding
  verified release while preserving D1 records and migrations. Do not drop the
  archive or remove its normal append-only triggers to resolve a UI failure.

Current plan specifications:
https://developers.cloudflare.com/workers/platform/limits/
https://developers.cloudflare.com/d1/platform/pricing/
