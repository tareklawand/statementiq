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
