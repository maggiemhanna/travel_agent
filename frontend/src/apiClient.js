/**
 * Resolves a frontend environment URL using 3-tier precedence:
 * 1. Cloud Run runtime injection (window.__ENV__)
 * 2. Vite build-time env (import.meta.env)
 * 3. Provided default fallback URL
 */
export function resolveBackendUrl(envKey, defaultUrl = '') {
  const runtimeVal = typeof window !== 'undefined' ? window.__ENV__?.[envKey] : '';
  const buildVal = import.meta.env?.[envKey];
  return (runtimeVal || buildVal || defaultUrl).trim().replace(/\/$/, '');
}

/**
 * Extracts a non-negative numeric flight price from currency-formatted strings
 * (e.g. "520 EUR", "$520", "€520", "£1,250.50"). Returns NaN when unparseable.
 */
export function parseFlightPrice(priceStr) {
  if (typeof priceStr === 'number') {
    return Number.isFinite(priceStr) && priceStr >= 0 ? priceStr : Number.NaN;
  }
  if (typeof priceStr !== 'string') {
    return Number.NaN;
  }
  const normalized = priceStr.replace(/,/g, '').trim();
  if (!normalized) {
    return Number.NaN;
  }
  const match = normalized.match(/-?\d+(?:\.\d+)?/);
  if (!match) {
    return Number.NaN;
  }
  const parsed = Number.parseFloat(match[0]);
  return parsed >= 0 ? parsed : Number.NaN;
}

/**
 * Executes a JSON POST request against primaryUrl and automatically fails over
 * once to fallbackUrl (warm secondary Cloud Run region) on network failure or
 * HTTP 5xx server error. 4xx client validation errors return immediately.
 */
export async function postWithRegionalFailover({
  primaryUrl,
  fallbackUrl = '',
  path,
  payload,
  fetchImpl = fetch,
}) {
  const primary = (primaryUrl || '').trim().replace(/\/$/, '');
  const fallback = (fallbackUrl || '').trim().replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  const hasDistinctFallback = Boolean(fallback && fallback !== primary);

  const requestInit = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  };

  try {
    const response = await fetchImpl(`${primary}${normalizedPath}`, requestInit);
    if (response.status >= 500 && hasDistinctFallback) {
      console.warn(
        `[RegionalFailover] Primary endpoint ${primary}${normalizedPath} returned HTTP ${response.status}. Retrying against warm secondary endpoint ${fallback}${normalizedPath}.`
      );
      return await fetchImpl(`${fallback}${normalizedPath}`, requestInit);
    }
    return response;
  } catch (networkErr) {
    if (!hasDistinctFallback) {
      throw networkErr;
    }
    console.warn(
      `[RegionalFailover] Primary endpoint ${primary}${normalizedPath} failed (${networkErr.message}). Failing over to warm secondary endpoint ${fallback}${normalizedPath}.`
    );
    return await fetchImpl(`${fallback}${normalizedPath}`, requestInit);
  }
}
