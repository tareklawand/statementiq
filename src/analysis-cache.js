// Only public GET analyses. Expiry follows the original source retrieval time.
export function analysisCacheKey(request, env) {
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.pathname !== '/api/analyze' || request.headers.has('authorization') ||
      [...url.searchParams.keys()].some(key => !['ticker', 'refresh'].includes(key))) return null;
  if (url.searchParams.getAll('ticker').length !== 1 || url.searchParams.getAll('refresh').length > 1) return null;
  const symbol = (url.searchParams.get('ticker') || '').trim().toUpperCase();
  const refresh = url.searchParams.get('refresh');
  if (refresh !== null && !['true','false'].includes(refresh.toLowerCase())) return null;
  if (!/^[A-Z0-9][A-Z0-9.\-]{0,23}$/.test(symbol)) return null;
  const key = new URL('/__public_analysis_cache', url.origin);
  key.searchParams.set('version', env.CF_VERSION_METADATA?.id || 'local-speed-1');
  key.searchParams.set('ticker', symbol);
  return new Request(key);
}

export async function readAnalysisCache(request, env, cache, now = Date.now()) {
  const key = analysisCacheKey(request, env);
  if (!key || !cache || new URL(request.url).searchParams.get('refresh')?.toLowerCase() === 'true') return null;
  try {
    const saved = await cache.match(key);
    const deadline = Number(saved?.headers.get('x-statementiq-cache-until'));
    if (!saved || !Number.isFinite(deadline) || deadline * 1000 <= now || deadline * 1000 > now + 300000) return null;
    const headers = new Headers(saved.headers);
    headers.set('cache-control', 'no-store');
    headers.set('x-statementiq-cache', 'hit');
    headers.delete('server-timing');
    return new Response(saved.body, {status: saved.status, headers});
  } catch { return null; } // A cache outage must never hide a valid source response.
}

export async function writeAnalysisCache(request, env, response, cache, now = Date.now()) {
  const key = analysisCacheKey(request, env);
  const deadline = Number(response.headers.get('x-statementiq-cache-until'));
  const ttl = Math.floor(deadline - now / 1000);
  if (!key || !cache || response.status !== 200 || !response.headers.get('content-type')?.includes('application/json') ||
      response.headers.has('set-cookie') || !Number.isFinite(ttl) || ttl <= 0 || ttl > 300) return;
  const headers = new Headers(response.headers);
  headers.set('cache-control', `public, max-age=${ttl}`);
  try { await cache.put(key, new Response(response.clone().body, {status: 200, headers})); }
  catch { /* Public analysis remains available if the local edge cache is full. */ }
}
