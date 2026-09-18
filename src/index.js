export default {
  async fetch(request, env) {
    const requestUrl = new URL(request.url);
    const isApiRequest =
      requestUrl.pathname.startsWith("/api/") ||
      requestUrl.pathname === "/health";

    // FastAPI serves browser files from /static locally. Cloudflare Assets
    // publishes the contents of that directory at the site root, so preserve
    // the same HTML paths by translating them at the edge.
    if (requestUrl.pathname.startsWith("/static/")) {
      requestUrl.pathname = requestUrl.pathname.slice("/static".length);
      return env.ASSETS.fetch(new Request(requestUrl, request));
    }

    if (!isApiRequest) {
      return env.ASSETS.fetch(request);
    }

    const upstreamUrl = new URL(
      `${requestUrl.pathname}${requestUrl.search}`,
      env.BACKEND_ORIGIN
    );

    try {
      const upstreamResponse = await fetch(new Request(upstreamUrl, request));
      const responseHeaders = new Headers(upstreamResponse.headers);
      responseHeaders.forEach((_, key) => {
        if (key === "server" || key.startsWith("x-render-")) {
          responseHeaders.delete(key);
        }
      });
      responseHeaders.set("x-content-type-options", "nosniff");

      return new Response(upstreamResponse.body, {
        status: upstreamResponse.status,
        statusText: upstreamResponse.statusText,
        headers: responseHeaders
      });
    } catch (error) {
      console.error(JSON.stringify({
        event: "backend_proxy_error",
        path: requestUrl.pathname,
        message: error instanceof Error ? error.message : "Unknown proxy error"
      }));

      return Response.json(
        {
          detail: "The financial engine is starting. Please try again in a moment."
        },
        {
          status: 502,
          headers: { "retry-after": "5" }
        }
      );
    }
  }
};
