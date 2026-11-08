# Reliability and performance audit — 2026-11-08

## Scope and operating evidence

Reviewed the shared company-fetch path, SEC metadata/facts/text retrieval,
validation caches, analysis and peer requests, DCF/model/PDF request handling,
Cloudflare caching/archive routes, deployment checks, and browser initialization.
Financial formula regression tests remain part of verification; this work is
not an independent financial audit or a claim that every future outage is solved.

The four scheduled availability checks since the 2026-11-07 wake-up correction
all passed: runs 42415684562, 42446030348, 42456719920 and 42481431010.
The last-24-hour Render error search showed successful warmups with
`source_error_code: null`, rather than a new application exception in those
results. Render displays a 512 MB memory / 0.15 CPU free instance limit.
Its detailed memory/CPU history is gated behind a paid compute plan, so this
audit does not claim an observed production memory peak or a proven OOM event.

Before changes, seven sequential live analyses returned HTTP200: AAPL, MSFT,
AMZN, NVDA, TSLA, DOCU and JPM. Uncached warm requests took 4.100–5.555 s;
cached Apple took 0.097 s. Source requests took about 3.2–4.6 s and analysis
calculation took about 0.5–0.7 s on the free server. These are observations,
not a cold-start or latency guarantee. JPM's institution-specific missing inputs
remain disclosed; no unsupported financial values are inferred to fill them.

## Findings and corrections

1. **Liveness shared the busy worker pool.** A controlled local reproduction
   occupied the synchronous worker capacity. The previous `/health` stalled
   beyond the 500 ms test deadline; the asynchronous health check returned 200
   in 3.86 ms under the same condition. Health and preset metadata no longer
   require a free financial-work thread. Increasing the worker count was avoided.

2. **The first source caller could wait much longer than duplicate callers.**
   Every caller now has the same bounded 20-second wait while the shared source
   work continues. At most two company jobs are admitted; there is no unbounded
   background queue. Refresh and ordinary requests for one company share a job.
   A retry rejoins existing work or reads its completed fresh cache. Cached data
   remains available even when both source slots are occupied. A timeout returns
   retryable busy status and never becomes financial evidence.

3. **Source limits were checked after allocation.** Annual filings were fully
   buffered before their 50 MiB limit was checked. Filing text now streams with
   decoded-byte counting before allocation exceeds the limit. SEC Company Facts
   uses a 24 MiB decoded-body ceiling and serialized full-history reads; existing
   concept filtering still occurs afterward. Oversized/failed reads close the
   response and remain explicitly unavailable, without changing reported values.
   Read timeouts and a cooperative body-processing budget remain in place.

4. **Other expensive work had no shared admission limit.** Four expensive API
   requests may run at once, including source waits. One annual text review,
   PDF or Excel document operation may run at a time. Excess work gets HTTP503
   with a five-second retry hint before doing the expensive work. Ordinary GET
   recovery remains bounded; forecast/report POSTs are not silently retried.
   Slots release on failures and completed streaming responses. Slow request-body
   uploads have a 15-second receive budget, and PDF requests now share the model
   endpoints' existing 64 KiB preparse body ceiling.

5. **Two auxiliary caches could grow indefinitely.** SEC metadata is bounded
   to 64 entries and phrase-review results to 32. Cache reads/writes are locked.
   A failed phrase-review cooldown starts when the attempt finishes, preventing
   a slow failure from expiring its own cooldown before a retry arrives.

6. **Presentation downloads blocked core initialization.** Plotly and icons now
   load as deferred, local versioned assets. Core navigation and analysis start
   after the local application modules load, without waiting for chart assets.
   Charts/icons refresh when their libraries arrive. A missing chart asset has
   an explicit fallback message while reported tables remain usable. The npm
   package SHA-512 integrity values were verified; asset SHA-256 records and
   license files are retained in `static/vendor`. The pre-existing Plotly version
   is preserved; Lucide is pinned to the current 1.70.0 release.

7. **Blocked browser storage could stop initialization.** Theme storage reads
   and writes are optional. Tests cover storage exceptions and duplicate startup
   events. The phone viewport (390 px) and tablet viewport (820 px) showed no
   document overflow; four charts rendered and the tablet DCF baseline loaded.

8. **Dependency compatibility needed an explicit boundary.** Render logged
   pandas-4 deprecation warnings inside the pinned Yahoo client. Pandas is now
   constrained below that incompatible major version. Requests and NumPy are
   declared directly because production modules import them, rather than relying
   on another package to install them. This is not a complete transitive lockfile;
   deployment regression checks still validate the resolved environment.

9. **Edge submission streams were not explicitly closed on extraction.** The
   SEC fallback now cancels a full-submission stream once its annual report is
   extracted, rather than leaving unrelated exhibits unread on an open stream.
   Malformed headers are capped at 64 Ki characters and extracted annual text at
   16 Mi characters, below the Worker's isolate-memory budget. One such review
   runs per isolate; excess work and connection failures return retryable JSON.
   These limits apply to optional phrase review, not structured financial rows.

The developer-specific local Python path was removed from the production entry
point. New source/resource handling files are included in methodology fingerprints.
Regression CI now covers `codex/**` branches before main publication.

## Verification and release

Final test, deployment and live-check records are appended after verification.
The existing provider validation, source freshness, integrity holds, formulas,
public-archive scope, private-download behavior and free billing plans remain.

External provider access restrictions and a sleeping free Render instance can
still delay a request. Capacity controls protect responsiveness by returning an
explicit temporary busy response; they do not create high-traffic capacity or
make free hosting equivalent to an always-running multi-instance service.

## Primary implementation references

- [Starlette's shared synchronous thread pool](https://starlette.dev/threadpool/)
- [Requests response streaming and closing](https://requests.readthedocs.io/en/latest/user/advanced/#body-content-workflow)
- [Deferred script behavior](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script#defer)
