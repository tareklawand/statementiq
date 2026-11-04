# Automatic statement updates

Each analysis request fetches filing metadata and selects statement inputs.
Ordinary cached responses are at most five minutes old; an explicit refresh
bypasses the analysis and filing-metadata caches. A changed SEC accession
invalidates the structured-facts cache immediately. Live analyses remain request-driven;
an already-open page does not silently replace its results. The public research
archive now has a separate bounded background filing checker, described below.

## Selection and safety

- A current Yahoo statement dataset remains usable with the existing SEC
  cross-check. This preserves standardized custom rows not in Company Facts.
- When any statement is missing or materially behind the latest verified SEC
  report period, consolidated standard US-GAAP Company Facts are imported.
- Current-period source facts must belong to the newest filing's accession;
  incomplete amendments and indexing delays do not silently reuse older facts.
- All imported statement frames come from SEC facts. Provider rows are never
  carried into a newer SEC period. Monetary units are not inferred from the
  exchange currency, and missing values are not zeroes.
- Annual periods use reported annual amounts. TTM monetary flows use a direct
  reported full-year interval or prior fiscal year + current YTD - comparable
  prior YTD. Discrete quarters use direct quarter facts or consecutive YTD
  subtraction. EPS and weighted-average shares are not subtracted or annualized.
- Payment facts are displayed as signed cash outflows. Provenance retains the
  original XBRL value and an explicit arithmetic coefficient for every source.
- Year-ago balance comparisons use actual dates rather than column positions.
- Balance-sheet reconciliation, matching periods, finite values, unique facts,
  supported forms and unambiguous currency are required. Score coverage and
  sector-applicability rules remain unchanged.
- Imported borrowings exclude lease liabilities. Missing borrowing components
  are not assumed to be zero. This definition is shown with source details.
- If import is unavailable, old provider inputs remain visibly dated and the
  freshness hold stays in force. It is never cleared merely to produce a score.

## Scope and limitations

Company Facts contains standard, entity-wide concepts, not every custom tag or
segment disclosure. This importer supports consolidated US-GAAP tags. IFRS,
custom-tag-only or incomplete datasets retain the provider path and safeguards.
It does not scrape arbitrary filing prose or invent a universal mapping.
Non-SEC companies still depend on the statement provider. Banks, insurers and
REITs still require their appropriate specialized evidence before a headline
score can be published. Prices and analyst targets remain market-provider data.

The API's `data_quality.sec_statement_import` exposes selected source tags,
units, periods, accessions, arithmetic and reconciliation checks. The financial
statements tab exposes source details without changing financial values.

SEC facts can be indexed after the filing metadata. A five-minute cache and
external network/provider outages can delay availability. These are transparent
data-integrity checks, not an independent financial audit.

Primary specification: https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## Persistent research archive

The free Cloudflare D1 archive captures supported SEC-only statement inputs,
derived analysis, source provenance, methodology code fingerprints and input
fingerprints. It excludes market quotes and private research. A content hash
identifies each frozen payload; duplicate retrievals preserve the first capture
time. SQL triggers reject record updates/deletions through normal application
access. Administrators retain control of the database, so this is not an
administrator-proof audit log or an independently validated financial audit.

Successful captures enroll the issuer in a background queue. Every 30 minutes
the Worker checks up to three due issuers against official SEC submissions and
attempts at most one complete import. This is a bounded free-tier job, not a
30-minute freshness guarantee for every company. The interface shows actual
check/capture times. Unchanged filings do not wake the Python service. Metadata
that appears before numeric facts remains pending and is retried on later jobs;
it is not marked successfully updated. Cold starts, indexing delays, outages,
quota limits and queue size can delay capture. Unsupported issuers are not
silently enrolled as successfully imported.

Snapshot capture dates describe observations made after activation. These
records do not reconstruct information known before they were collected.

## Verification

`python3 -m pytest tests/test_sec_statement_importer.py` covers annual rollover,
YTD/quarter/TTM arithmetic, missing rows, conflicting facts, currency ambiguity,
incomplete latest accessions, balance reconciliation, cache invalidation,
arbitrary tickers and the recency hold. Existing integrity, metrics, API and
frontend tests must also pass before deployment.
