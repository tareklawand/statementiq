# Visitor startup recovery — 2026-11-06

The owner reported a roughly two-minute cold load of the automatic Apple
analysis. That exact incident was not reproduced: the service was already awake
when checked. A forced live Apple refresh returned HTTP200 in 4.071 seconds,
with Server-Timing reporting 3.174 seconds for sources and 0.604 for calculations.
The earlier five-second measurements were warm-server observations, not cold
startup guarantees.

## Avoidable startup delays

Previously, the separate direct-origin health request only ran after an analysis
request failed. One stalled attempt can last 75 seconds. Exponential recovery
also reached roughly 30-second gaps, leaving a visitor waiting even if the
origin became ready between attempts. This is a code-path finding, not proof
that either condition caused the reported incident.

A direct #workspace visit now starts one shared, nonblocking health request
before external fonts, chart and icon downloads. Opening the workspace from the
landing page also starts it immediately. It does not poll periodically, keep
Render awake, or treat an opaque health response as readiness or financial data.
Only the validated analysis response can populate the dashboard.

Analysis and preset recovery use gaps capped at five seconds for startup/network
failures, within the existing three-minute total budget. The attempt limit is
adjusted so short gaps do not exhaust recovery before a sleeping service wakes.
429 backoff and every explicit Retry-After cooldown are preserved. Other research
requests retain their existing retry behavior. A blocked health probe cannot
block the analysis request or replace its outcome.

The financial source, freshness window, missing-data protections and calculation
logic are unchanged. Free-host startup latency is still outside this code's
control. No restart, upgrade, new account or background keep-alive was requested.

## Verification

- 51 Node checks passed, including a simulated 70-second unavailable origin
  observed ready within five further seconds, bounded persistent failures,
  cooldown/rate-limit preservation, one startup request per visit, cancellation,
  automatic Apple initialization and script ordering before presentation assets.
- Two frontend structure checks passed. No financial calculation files changed.
- Live publication and browser verification are recorded after deployment below.
