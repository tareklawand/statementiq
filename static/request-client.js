// Shared, bounded recovery for read-only requests. Never retry report POSTs.
const StatementIQRequests = (() => {
    const transientStatuses = new Set([408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524]);
    let startupPromise = null;
    let visitStartupPromise = null;

    class RequestError extends Error {
        constructor(message, { status = 0, retryable = false, retryAfterMs = 0 } = {}) {
            super(message);
            this.name = "RequestError";
            this.status = status;
            this.retryable = retryable;
            this.retryAfterMs = retryAfterMs;
        }
    }

    function abortError() {
        return new DOMException("Request cancelled", "AbortError");
    }

    function retryAfterDelay(value) {
        if (!value) return 0;
        const seconds = Number(value);
        if (Number.isFinite(seconds) && seconds >= 0) return seconds * 1000;
        const date = Date.parse(value);
        return Number.isFinite(date) ? Math.max(0, date - Date.now()) : 0;
    }

    function wait(milliseconds, signal) {
        return new Promise((resolve, reject) => {
            if (signal?.aborted) return reject(abortError());
            const onAbort = () => {
                clearTimeout(timer);
                reject(abortError());
            };
            const timer = setTimeout(() => {
                signal?.removeEventListener("abort", onAbort);
                resolve();
            }, milliseconds);
            signal?.addEventListener("abort", onAbort, { once: true });
        });
    }

    async function requestJson(url, {
        signal,
        onRetry = () => {},
        validate = () => true,
        startupRecovery = false,
        maxAttempts = startupRecovery ? 36 : 8,
        maxElapsedMs = 180000,
        attemptTimeoutMs = 75000,
    } = {}) {
        const deadline = Date.now() + maxElapsedMs;
        let lastError;

        for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
            if (signal?.aborted) throw abortError();
            const remaining = deadline - Date.now();
            if (remaining <= 0) break;
            const controller = new AbortController();
            const onAbort = () => controller.abort();
            signal?.addEventListener("abort", onAbort, { once: true });
            const timer = setTimeout(() => controller.abort(), Math.min(attemptTimeoutMs, remaining));

            try {
                const response = await fetch(url, {
                    signal: controller.signal,
                    headers: { Accept: "application/json" },
                    cache: "no-store",
                });
                if (!response.ok) {
                    let detail = "The analysis service is temporarily unavailable.";
                    if (!transientStatuses.has(response.status)) {
                        try {
                            const payload = await response.json();
                            if (typeof payload.detail === "string") detail = payload.detail.slice(0, 500);
                        } catch (_) { /* Hosting error pages need not contain JSON. */ }
                    } else {
                        await response.body?.cancel();
                    }
                    throw new RequestError(detail, {
                        status: response.status,
                        retryable: transientStatuses.has(response.status),
                        retryAfterMs: retryAfterDelay(response.headers.get("retry-after")),
                    });
                }

                let payload;
                try {
                    payload = await response.json();
                } catch (_) {
                    throw new RequestError("The analysis service returned an incomplete response.", { retryable: true });
                }
                if (!payload || typeof payload !== "object" || !validate(payload)) {
                    throw new RequestError("The analysis service returned an incomplete response.", { retryable: true });
                }
                return payload;
            } catch (error) {
                if (signal?.aborted) throw abortError();
                lastError = error instanceof RequestError ? error : new RequestError(
                    "The connection to the analysis service was interrupted.", { retryable: true }
                );
                if (!lastError.retryable) throw lastError;
            } finally {
                clearTimeout(timer);
                signal?.removeEventListener("abort", onAbort);
            }

            if (attempt === maxAttempts) break;
            const backoff = Math.min(30000, 2000 * (2 ** (attempt - 1)));
            const jitteredBackoff = Math.round(backoff * (0.9 + Math.random() * 0.2));
            // During a visitor's startup, check again promptly rather than
            // sleeping for 30 seconds after the origin has become ready. Rate
            // limits and explicit provider cooldowns retain their full delay.
            const retryGap = startupRecovery && lastError.status !== 429
                ? Math.min(5000, jitteredBackoff) : jitteredBackoff;
            const delay = Math.max(lastError.retryAfterMs, retryGap);
            // Respect the server's cooldown instead of retrying early or waiting forever.
            if (Date.now() + delay >= deadline) break;
            onRetry({ attempt, delayMs: delay, status: lastError.status });
            await wait(delay, signal);
        }

        throw lastError || new RequestError("The analysis service took too long to respond.", { retryable: true });
    }

    function wakeService() {
        if (startupPromise) return startupPromise;
        startupPromise = (async () => {
            const config = await requestJson("/api/startup-config", {
                maxAttempts: 1, maxElapsedMs: 5000, attemptTimeoutMs: 5000,
                validate: payload => typeof payload.startup_url === "string"
                    && new URL(payload.startup_url).protocol === "https:",
            });
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 90000);
            try {
                // A single visitor-initiated health request can wake a sleeping
                // origin when its edge is refusing the proxied request. The
                // opaque response is NOT treated as readiness or financial data.
                await fetch(config.startup_url, {
                    mode: "no-cors", credentials: "omit", referrerPolicy: "no-referrer",
                    cache: "no-store", signal: controller.signal,
                });
            } finally {
                clearTimeout(timer);
            }
        })().catch(() => {
            // The ordinary API retry remains the sole readiness check. A
            // blocked startup probe must not overwrite its result or error.
        }).finally(() => { startupPromise = null; });
        return startupPromise;
    }

    function beginVisit() {
        // The early page script and workspace share one startup request. It
        // neither blocks rendering nor runs periodically to keep a host awake.
        if (!visitStartupPromise) visitStartupPromise = wakeService();
        return visitStartupPromise;
    }

    return { requestJson, wakeService, beginVisit, RequestError };
})();
