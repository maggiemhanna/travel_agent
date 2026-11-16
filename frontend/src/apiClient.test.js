import assert from 'node:assert/strict';
import test from 'node:test';

import { parseFlightPrice, postWithRegionalFailover, resolveBackendUrl } from './apiClient.js';

const PRIMARY_URL = 'https://flights-paris.a.run.app';
const FALLBACK_URL = 'https://flights-belgium.a.run.app';

test('resolveBackendUrl enforces runtime window.__ENV__ precedence and strips trailing slashes', () => {
  const prevWindow = globalThis.window;
  try {
    delete globalThis.window;
    assert.equal(
      resolveBackendUrl('VITE_FLIGHTS_SEARCH_API_URL', 'http://127.0.0.1:8000/'),
      'http://127.0.0.1:8000'
    );

    globalThis.window = {
      __ENV__: {
        VITE_FLIGHTS_SEARCH_API_URL: '  https://prod-paris.a.run.app/  ',
      },
    };
    assert.equal(
      resolveBackendUrl('VITE_FLIGHTS_SEARCH_API_URL', 'http://127.0.0.1:8000'),
      'https://prod-paris.a.run.app'
    );
  } finally {
    if (prevWindow === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = prevWindow;
    }
  }
});

test('postWithRegionalFailover returns primary 200 OK without calling warm secondary region', async () => {
  const calls = [];
  const mockFetch = async (url, init) => {
    calls.push({ url, method: init.method });
    return { ok: true, status: 200, json: async () => ({ status: 'success' }) };
  };

  const resp = await postWithRegionalFailover({
    primaryUrl: `${PRIMARY_URL}/`,
    fallbackUrl: `${FALLBACK_URL}/`,
    path: 'run-flights-search',
    payload: { origin: 'Paris' },
    fetchImpl: mockFetch,
  });

  assert.equal(resp.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, `${PRIMARY_URL}/run-flights-search`);
});

test('postWithRegionalFailover automatically fails over to warm secondary region on HTTP 503', async () => {
  const calls = [];
  const mockFetch = async (url) => {
    calls.push(url);
    if (url.startsWith(PRIMARY_URL)) {
      return { ok: false, status: 503 };
    }
    return { ok: true, status: 200, json: async () => ({ region: 'europe-west1' }) };
  };

  const resp = await postWithRegionalFailover({
    primaryUrl: PRIMARY_URL,
    fallbackUrl: FALLBACK_URL,
    path: '/run-conversational',
    payload: { user_message: 'hello' },
    fetchImpl: mockFetch,
  });

  assert.equal(resp.status, 200);
  assert.deepEqual(calls, [
    `${PRIMARY_URL}/run-conversational`,
    `${FALLBACK_URL}/run-conversational`,
  ]);
});

test('postWithRegionalFailover automatically fails over on primary network TypeError', async () => {
  const calls = [];
  const mockFetch = async (url) => {
    calls.push(url);
    if (url.startsWith(PRIMARY_URL)) {
      throw new TypeError('Failed to fetch');
    }
    return { ok: true, status: 200 };
  };

  const resp = await postWithRegionalFailover({
    primaryUrl: PRIMARY_URL,
    fallbackUrl: FALLBACK_URL,
    path: '/run-flights-search',
    payload: { origin: 'Paris' },
    fetchImpl: mockFetch,
  });

  assert.equal(resp.status, 200);
  assert.deepEqual(calls, [
    `${PRIMARY_URL}/run-flights-search`,
    `${FALLBACK_URL}/run-flights-search`,
  ]);
});

test('postWithRegionalFailover does NOT retry warm secondary region on HTTP 422 client validation error', async () => {
  const calls = [];
  const mockFetch = async (url) => {
    calls.push(url);
    return { ok: false, status: 422 };
  };

  const resp = await postWithRegionalFailover({
    primaryUrl: PRIMARY_URL,
    fallbackUrl: FALLBACK_URL,
    path: '/run-conversational',
    payload: {},
    fetchImpl: mockFetch,
  });

  assert.equal(resp.status, 422);
  assert.deepEqual(calls, [`${PRIMARY_URL}/run-conversational`]);
});

test('postWithRegionalFailover skips redundant retry when fallbackUrl is empty or identical, and propagates dual outage', async () => {
  let singleRegionCalls = 0;
  await assert.rejects(
    () =>
      postWithRegionalFailover({
        primaryUrl: PRIMARY_URL,
        fallbackUrl: PRIMARY_URL,
        path: '/run-flights-search',
        payload: {},
        fetchImpl: async () => {
          singleRegionCalls += 1;
          throw new TypeError('DNS failure');
        },
      }),
    /DNS failure/
  );
  assert.equal(singleRegionCalls, 1);

  let dualOutageCalls = 0;
  await assert.rejects(
    () =>
      postWithRegionalFailover({
        primaryUrl: PRIMARY_URL,
        fallbackUrl: FALLBACK_URL,
        path: '/run-flights-search',
        payload: {},
        fetchImpl: async () => {
          dualOutageCalls += 1;
          throw new TypeError('Both regions unreachable');
        },
      }),
    /Both regions unreachable/
  );
  assert.equal(dualOutageCalls, 2);
});

test('parseFlightPrice handles multi-currency formats and safely rejects malformed/degraded strings', () => {
  assert.equal(parseFlightPrice('520 EUR'), 520);
  assert.equal(parseFlightPrice('$520'), 520);
  assert.equal(parseFlightPrice('€520'), 520);
  assert.equal(parseFlightPrice('£1,250.50'), 1250.5);
  assert.equal(parseFlightPrice('USD 780'), 780);
  assert.equal(parseFlightPrice(640), 640);

  assert.ok(Number.isNaN(parseFlightPrice('')));
  assert.ok(Number.isNaN(parseFlightPrice('N/A')));
  assert.ok(Number.isNaN(parseFlightPrice('-50 USD')));
  assert.ok(Number.isNaN(parseFlightPrice(null)));
  assert.ok(Number.isNaN(parseFlightPrice(undefined)));

  const sampleFlights = [
    { flight_number: 'AF006', price: '€520' },
    { flight_number: 'DL265', price: '$610' },
    { flight_number: 'UA057', price: '820 EUR' },
    { flight_number: 'BROKEN', price: 'unavailable' },
  ];
  const under650 = sampleFlights.filter((f) => parseFlightPrice(f.price) <= 650);
  assert.deepEqual(
    under650.map((f) => f.flight_number),
    ['AF006', 'DL265']
  );
});

