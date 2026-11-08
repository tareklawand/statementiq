# Search discovery changes — 9 November 2026

Scope: organic search discovery for StatementIQ. No hosting subscription, paid SEO service, account system, financial calculation, or data-provider change.

## Public content

The homepage now names the actual product and its existing capabilities in visible text. Five static pages explain the product, founder, sources, model limitations, statement analysis, financial ratios, and DCF valuation:

- `/about`
- `/methodology`
- `/guides/financial-statement-analysis`
- `/guides/financial-ratios`
- `/guides/dcf-valuation`

Every page is linked from the homepage, has its own title, description, canonical URL, social metadata, and JSON-LD. Breadcrumbs and cross-links connect the resource pages. The existing chosen IQ logo is retained. The founder and company-statement scope are stated visibly to help distinguish this product from unrelated bank-statement converters with the same name. No rankings, reviews, credentials, or financial results are invented.

Pages are delivered from Cloudflare static assets. They do not load the chart library or initialize the Python analysis service. Public content remains present without JavaScript. The small theme helper has no backend calls and tolerates unavailable browser storage.

## Routing and crawling

- Sitemap lists the six real canonical pages and their content modification date.
- Robots permits public crawling, while excluding analysis API and health routes. Existing API noindex headers remain in place.
- Unknown addresses return an actual 404 page, replacing the previous homepage response with status 200. The workspace continues to use `/#workspace`, so it does not depend on path fallback.
- `/static/index.html` redirects to `/`; Cloudflare also canonicalizes `.html` and trailing-slash variants.
- No firewall or bot-security setting is changed. A request with a crawler user-agent only checks that request's response; it does not verify the real crawler's IP-based access.

## Validation

- 65 JavaScript checks passed, including sitemap/metadata consistency, local-link targets, static-only page delivery, preserved 404 status, and blocked-storage theme handling.
- Two existing Python frontend-structure checks passed.
- Local Cloudflare preview returned 200 for all six sitemap pages; `.html` and slash variants resolved to the canonical paths; unknown document and asset addresses returned 404.
- Browser checks cover the homepage, methodology page, ratio table and DCF guide in light/dark themes and phone/tablet layouts. Final publication checks are recorded in the release note below.

## Search guidance

Google says its standard SEO requirements also apply to AI Overviews and AI Mode; no special AI schema or extra machine-readable AI file is required. Public, useful textual content and valid structured data make the product easier to understand, but do not guarantee indexing, rank, or AI citation. OpenAI documents OAI-SearchBot as its search crawler, separately from GPTBot's training use. The existing public crawl permission is retained; no new training-specific permission is added.

References:

- https://developers.google.com/search/docs/fundamentals/seo-starter-guide
- https://developers.google.com/search/docs/appearance/ai-features
- https://developers.openai.com/api/docs/bots
- https://developers.cloudflare.com/workers/static-assets/routing/advanced/html-handling/
- https://www.sec.gov/investor/pubs/begfinstmtguide.htm
- https://pages.stern.nyu.edu/~adamodar/New_Home_Page/littlebook/terminalvalue.htm

The methodology copy was checked against `data_fetcher.py`, `metrics_calculator.py`, and `forecast_model.py`; it describes supported behavior and does not claim universal sector coverage or independently audited financial data.

## Release verification

Published code: `ac83961`. Cloudflare Worker version: `5e05d102-9258-4bc9-8139-2f7bdece6ba7`.

All three repository checks passed before publication (Python 3.11, Python 3.14, browser regression): https://github.com/tareklawand/statementiq/actions/runs/42531891869

Live checks returned 200 for all six sitemap pages and their expected canonical metadata. `.html`, trailing-slash, and old local-homepage variants resolved to the canonical addresses. An unknown page and asset returned 404. `/api/startup-config` retained `noindex, nofollow`. Public robots responses returned 200 for requests using Googlebot and OAI-SearchBot user-agent strings; this does not establish access from their actual crawler IPs. No Search Console recrawl request or sitemap submission was made in this change; the public sitemap URL is unchanged and contains the expanded page list.

The published homepage was also verified in the browser. A screenshot was saved locally to the SEO task's output folder. No hosting plan or billing change was made, and the publication did not require restarting the Python backend.

For the Cloudflare page-routing preview, run `wrangler dev --host 127.0.0.1`; the API-only Python server is not the public-page router for these added paths.
