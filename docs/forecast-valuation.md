# Public forecasts, DCF and downloads

The Forecast & DCF tab is public and does not require an account. Direct entry:
https://statementiq-lb.com/?tool=dcf#workspace

Published and verified on 2026-11-05, including the public calculation and Excel
export routes. See the dated release-verification record for deployment evidence.

## Reported inputs

The server fetches the company and prefers supported SEC statement evidence.
Income and cash-flow inputs use the latest aligned TTM or annual flows; the
balance sheet uses the matching latest quarter or annual date. Misaligned inputs
are withheld instead of silently reverting to an older annual set. The valuation
is at that reported baseline date, not today's quote or an intra-year stub. Fiscal anniversary forecast dates are modeled
period ends, not confirmed future filing calendars. Monetary units, borrowing
definitions and point-in-time common shares are explicit. Weighted-average EPS
shares never substitute for missing common shares. No missing opening inputs
are replaced with zero. Non-SEC/provider inputs require explicit current and
long-term borrowing rows rather than ambiguous combined lease/debt balances.

A source fingerprint is checked again before calculation or Excel export. If
reported inputs change, the request is rejected until the user reloads and
reviews the baseline. Client-supplied actual statements are never accepted.

## Financial model

Each of five years has separate user-entered growth, margins, tax, capex, D&A,
stock compensation, working-capital days and financing/distribution assumptions.
The historical-copy and no-financing controls are explicit user choices, never
silent defaults. Interest uses average debt. Equity includes net income, stock
compensation and explicit equity/distribution flows. Cash rolls from operating,
investing and financing flows without an automatic debt or equity plug.

FCFF = EBIT minus modeled unlevered tax + D&A − capex − change in noncash working
capital. Stock compensation stays an operating expense for DCF. Terminal NOPAT
uses final forecast operating economics and terminal growth. Terminal reinvestment
rate = terminal growth / terminal ROIC. Terminal FCFF = terminal NOPAT times
(1 − reinvestment rate); terminal value = terminal FCFF / (WACC − growth).
Discounting is annual at year-end, using constant user-entered WACC. The equity
bridge uses selected cash, additional nonoperating assets, reported book
borrowings and user-entered other claims. It does not silently value missing
preferred stock, minority interests or other claims at zero.

Method references:
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/definitions.html
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/valquestions/termvalueexreturns.htm

The model is for supported operating companies and utilities. Banks, insurers,
REITs and unverified company types require different evidence/models. The
simplified build holds other liabilities constant and rolls other noncash assets
only through capex and D&A. It has no NOL, OCI, FX, acquisition, disposal or
minority-interest schedules. It withholds valuation for unfunded cash deficits or
nonpositive terminal cash flow. Financial-health results are never recalculated
from forecasts.

## Downloads and privacy

Excel exports contain editable assumptions, linked statement and DCF formulas,
reported source rows, independent reconciliation checks and methodology notes.
The existing Python hosting cannot install the bundled private artifact engine
from the public package registry. A pinned openpyxl writer therefore generates
portable formulas; local QA imports and independently recalculates those exports
with the bundled spreadsheet engine, including edited-input and missing-input
checks. Excel is set to recalculate on opening. No macro, external data connection
or private account is required.

Research-package JSON includes the analysis, notes and original note context.
Model JSON includes its dated source baseline, assumptions and projected results.
Notes stay in browser memory; switching companies preserves notes for that open
page. Closing the page clears them unless downloaded. Forecast requests are
processed by the existing analysis service and are not saved to public D1.

## Operational checks

The research-operations workflow uses only public APIs and a read-only repository
permission. It does not need new Cloudflare/GitHub credentials. Public archive
backups preserve canonical payload bytes and verify every SHA-256 identifier.
The restore verifier reconstructs immutable snapshot records in isolated SQLite.
It does not roll back production or claim to restore historical operational logs.
Backups are daily, with seven-day artifact retention and a 15 MiB upload cap.
The service/data check runs every three hours. Failures are visible in GitHub
Actions and through the owner's existing GitHub notification settings. Schedules
may be delayed or disabled after repository inactivity. An independent review,
licensed institutional market data and an availability SLA remain external work.
