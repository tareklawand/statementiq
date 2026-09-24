const CANONICAL_HOSTNAME = "statementiq-lb.com";

function applyPublicHeaders(response, { preventIndexing = false } = {}) {
  const headers = new Headers(response.headers);
  headers.set("x-content-type-options", "nosniff");
  headers.set("referrer-policy", "strict-origin-when-cross-origin");
  headers.set("permissions-policy", "camera=(), microphone=(), geolocation=()");
  headers.set("strict-transport-security", "max-age=31536000; includeSubDomains");
  if (preventIndexing) {
    headers.set("x-robots-tag", "noindex, nofollow");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers
  });
}

export default {
  async fetch(request, env) {
    const requestUrl = new URL(request.url);
    const isPublicHostname =
      requestUrl.hostname === CANONICAL_HOSTNAME ||
      requestUrl.hostname === `www.${CANONICAL_HOSTNAME}` ||
      requestUrl.hostname.endsWith(".workers.dev");

    if (
      isPublicHostname &&
      (requestUrl.hostname !== CANONICAL_HOSTNAME || requestUrl.protocol !== "https:")
    ) {
      requestUrl.protocol = "https:";
      requestUrl.hostname = CANONICAL_HOSTNAME;
      requestUrl.port = "";
      return Response.redirect(requestUrl.toString(), 301);
    }

    const isApiRequest =
      requestUrl.pathname.startsWith("/api/") ||
      requestUrl.pathname === "/health";

    if (requestUrl.pathname === "/api/sec-ticker-map") {
      if (request.method !== "GET") {
        return applyPublicHeaders(Response.json({ detail: "Method not allowed" }, { status: 405 }), { preventIndexing: true });
      }
      const secHeaders = {
        "user-agent": "StatementIQ/1.0 statementiq-lb.com",
        "accept": "application/json,text/plain;q=0.9",
        "accept-language": "en-US,en;q=0.9"
      };
      let mapResponse = await fetch("https://www.sec.gov/files/company_tickers.json", {
        headers: secHeaders,
        cf: { cacheEverything: true, cacheTtl: 86400 }
      });
      if (mapResponse.status === 403 || mapResponse.status === 429) {
        const textResponse = await fetch("https://www.sec.gov/include/ticker.txt", {
          headers: secHeaders,
          cf: { cacheEverything: true, cacheTtl: 86400 }
        });
        if (!textResponse.ok) {
          return applyPublicHeaders(new Response(textResponse.body, { status: textResponse.status }), { preventIndexing: true });
        }
        const lines = (await textResponse.text()).split(/\r?\n/).filter(Boolean);
        const normalized = {};
        lines.forEach((line, index) => {
          const [ticker, cik] = line.split("\t");
          if (ticker && /^\d+$/.test(cik || "")) {
            normalized[index] = { ticker: ticker.toUpperCase(), cik_str: Number(cik), title: null };
          }
        });
        mapResponse = Response.json(normalized);
      }
      const headers = new Headers({
        "content-type": "application/json; charset=utf-8",
        "cache-control": "public, max-age=86400"
      });
      return applyPublicHeaders(new Response(mapResponse.body, { status: mapResponse.status, headers }), { preventIndexing: true });
    }

    // Render hosting IPs can be rate-limited by the SEC archive even while
    // SEC data endpoints remain available. This narrowly scoped edge route
    // fetches only official filing documents; it is not a general web proxy.
    if (requestUrl.pathname === "/api/sec-filing-text") {
      if (request.method !== "GET") {
        return applyPublicHeaders(Response.json({ detail: "Method not allowed" }, { status: 405 }), { preventIndexing: true });
      }
      let sourceUrl;
      try {
        sourceUrl = new URL(requestUrl.searchParams.get("url") || "");
      } catch (error) {
        return applyPublicHeaders(Response.json({ detail: "Invalid SEC filing URL" }, { status: 400 }), { preventIndexing: true });
      }
      const validArchivePath = /^\/Archives\/edgar\/data\/\d+\/[A-Za-z0-9._\/-]+$/i.test(sourceUrl.pathname);
      const validDocumentType = /\.(?:html?|txt)$/i.test(sourceUrl.pathname);
      if (
        sourceUrl.protocol !== "https:" ||
        sourceUrl.hostname !== "www.sec.gov" ||
        !validArchivePath ||
        !validDocumentType
      ) {
        return applyPublicHeaders(Response.json({ detail: "Only official SEC filing documents are allowed" }, { status: 400 }), { preventIndexing: true });
      }
      const secHeaders = {
        "user-agent": "StatementIQ/1.0 statementiq-lb.com",
        "accept": "text/html,text/plain;q=0.9",
        "accept-language": "en-US,en;q=0.9"
      };
      let secResponse = await fetch(sourceUrl.toString(), {
        headers: secHeaders,
        cf: { cacheEverything: true, cacheTtl: 21600 }
      });
      // The SEC archive sometimes blocks primary HTML for data-center IPs but
      // serves the official full-submission text. Derive that URL only from a
      // validated EDGAR accession directory.
      if (secResponse.status === 403 || secResponse.status === 429) {
        const pathParts = sourceUrl.pathname.split("/").filter(Boolean);
        const accessionCompact = pathParts[4] || "";
        if (/^\d{18}$/.test(accessionCompact)) {
          const accessionDashed = `${accessionCompact.slice(0, 10)}-${accessionCompact.slice(10, 12)}-${accessionCompact.slice(12)}`;
          const textUrl = new URL(sourceUrl.toString());
          textUrl.pathname = `/Archives/edgar/data/${pathParts[3]}/${accessionCompact}/${accessionDashed}.txt`;
          textUrl.search = "";
          secResponse = await fetch(textUrl.toString(), {
            headers: secHeaders,
            cf: { cacheEverything: true, cacheTtl: 21600 }
          });
        }
      }
      const contentLength = Number(secResponse.headers.get("content-length") || 0);
      if (contentLength > 50 * 1024 * 1024) {
        return applyPublicHeaders(Response.json({ detail: "SEC filing exceeds review size limit" }, { status: 413 }), { preventIndexing: true });
      }
      const headers = new Headers({
        "content-type": secResponse.headers.get("content-type") || "text/html; charset=utf-8",
        "cache-control": "public, max-age=21600"
      });
      return applyPublicHeaders(new Response(secResponse.body, { status: secResponse.status, headers }), { preventIndexing: true });
    }

    // FastAPI serves browser files from /static locally. Cloudflare Assets
    // publishes the contents of that directory at the site root, so preserve
    // the same HTML paths by translating them at the edge.
    if (requestUrl.pathname.startsWith("/static/")) {
      requestUrl.pathname = requestUrl.pathname.slice("/static".length);
      const assetResponse = await env.ASSETS.fetch(new Request(requestUrl, request));
      return applyPublicHeaders(assetResponse);
    }

    if (!isApiRequest) {
      const assetResponse = await env.ASSETS.fetch(request);
      return applyPublicHeaders(assetResponse);
    }

    const upstreamUrl = new URL(
      `${requestUrl.pathname}${requestUrl.search}`,
      env.BACKEND_ORIGIN
    );

    try {
      const upstreamResponse = await fetch(new Request(upstreamUrl, request));
      const responseHeaders = new Headers(upstreamResponse.headers);
      responseHeaders.forEach((_, key) => {
        if (key === "server" || key === "rndr-id" || key.startsWith("x-render-")) {
          responseHeaders.delete(key);
        }
      });
      const response = new Response(upstreamResponse.body, {
        status: upstreamResponse.status,
        statusText: upstreamResponse.statusText,
        headers: responseHeaders
      });
      return applyPublicHeaders(response, { preventIndexing: true });
    } catch (error) {
      console.error(JSON.stringify({
        event: "backend_proxy_error",
        path: requestUrl.pathname,
        message: error instanceof Error ? error.message : "Unknown proxy error"
      }));

      const response = Response.json(
        {
          detail: "The financial engine is starting. Please try again in a moment."
        },
        {
          status: 502,
          headers: { "retry-after": "5" }
        }
      );
      return applyPublicHeaders(response, { preventIndexing: true });
    }
  }
};
