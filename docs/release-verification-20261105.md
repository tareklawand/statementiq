# Forecast and research release verification — 2026-11-05

## Verified implementation

- Full Python suite: 109 passed, including live public-source API and PDF checks.
- Node suite: 40 passed, covering recovery, request cancellation, stale forecast
  responses, archive checksums and fixed-cutoff pagination.
- Real AAPL baseline: latest annual 2026-09-26; five-year calculation and Excel
  response succeeded using explicitly labelled software-verification assumptions.
- The bundled spreadsheet engine independently recalculated all 34 forecast
  lines for all five years and the enterprise/equity/per-share DCF results. WACC
  and growth edits recalculated correctly; missing source cash, growth or WACC
  withheld results. Formula error scan returned zero matches. All six workbook
  sheets were rendered and visually inspected. Native Microsoft Excel was not
  used as the verification engine.
- Latest-quarter selection: live MSFT uses 2026-09-30 TTM flows and quarterly
  balances instead of its older annual statements. Its DCF is correctly withheld
  because complete explicit borrowing components are absent from imported facts.
  No absent short-term borrowing figure was assumed to be zero. JPM is withheld
  by the operating-company model's applicability and source-integrity guards.
- Direct DCF entry, blank assumptions, historical-copy controls, explicit
  financing choices, calculation and Excel download were exercised in browser.
  Phone 390 × 844 and tablet 834 × 1112 layouts and dark mode were inspected.
- Local public archive backup: four immutable snapshots; isolated SQLite restore
  integrity and all payload checksums passed. Tampered backups fail tests and do
  not replace a prior completed backup.

## Publication and production verification

GitHub rejected main and two separate new-branch pushes with:
`remote: fatal error in commit_refs`. The remote main stayed at
`cdba16b0b9c74cd404a74edb42b06b90d11db314`. A separate software-only branch
without the new workflow failed identically. No force push, repository visibility
change, credential change or paid upgrade was attempted.

The push succeeded on retry, publishing source revision 69d6c3f. Render's
dashboard confirmed that revision live, with automatic deployments preserved.
The matching Cloudflare release is 622be36b-3eb2-4929-9092-095464525d0e.

Public-domain checks passed: AAPL baseline ready at 2026-09-26, forecast HTTP200,
Excel export HTTP200 with valid linked formulas and reported SEC revenue. The
production archive contained three snapshots; every checksum and issuer record
passed isolated SQLite restoration. The first GitHub Actions public-service and
public-sec-backup jobs both completed successfully:
https://github.com/tareklawand/statementiq/actions/runs/42062822047
The retained artifact public-sec-evidence-42062822047 was 83,385 bytes and expires
2026-11-12, confirming seven-day retention. Its job verified restoration before
upload. The independently downloaded production backup also restored correctly.

The public Forecast & DCF tab loaded the dated SEC baseline with empty future
assumptions. Calculation and the actual browser download were verified with
clearly labelled software-test assumptions. Financial-health actuals remained
separate. No user models or notes were written into the public archive.

## Future releases

1. From the isolated release clone, fetch origin and inspect any newer work.
   Publish the complete release without pushing the original project's unrelated
   unpublished commits. Never force-update main.
2. Wait for Render to deploy the complete source, including forecast_model.py,
   model_export.py, model_requests.py and the pinned openpyxl dependency. Verify
   model baseline, forecast and export routes before publishing the interface.
3. Deploy the matching Cloudflare Worker/assets with its existing D1 binding and
   cron configuration. No additional migration is needed for this release.
4. Verify production DCF entry, latest baseline date, calculation, actual Excel
   download, catalog pagination and exact canonical snapshot checksums.
5. Verify both GitHub Actions jobs succeed and restore the resulting public SEC
   artifact in isolated SQLite before claiming scheduled backups are active.
6. Update this verification record only after these checks succeed.

No accounts were added. The repository remains public and existing free plans
remain in use. Independent financial/model/security review, appropriate market
data rights and an enterprise availability commitment remain external work.
