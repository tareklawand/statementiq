# Automatic statement updates

Each analysis request fetches filing metadata and selects statement inputs.
Ordinary cached responses are at most five minutes old; an explicit refresh
bypasses the analysis and filing-metadata caches. A changed SEC accession
invalidates the structured-facts cache immediately. This is request-driven,
not a background scheduler or a promise that an already-open page refreshes.

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

## Verification

`python3 -m pytest tests/test_sec_statement_importer.py` covers annual rollover,
YTD/quarter/TTM arithmetic, missing rows, conflicting facts, currency ambiguity,
incomplete latest accessions, balance reconciliation, cache invalidation,
arbitrary tickers and the recency hold. Existing integrity, metrics, API and
frontend tests must also pass before deployment.
