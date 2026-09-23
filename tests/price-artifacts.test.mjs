import assert from 'node:assert/strict';
import test from 'node:test';
import { artifact, publishArtifact } from '../scripts/price-artifacts.mjs';
import { priceArtifactResponse, validPriceDate } from '../src/lib/price-artifact.mjs';

const row = artifact('2026-09-23', '<html><body>가격 그래프</body></html>');
const options = (result) => ({ url: 'https://db.invalid', key: 'fixture', fetchImpl: async () => result });

test('date validation rejects overflow and route injection', () => {
  for (const value of ['2026-02-30', '2026-13-01', '../latest', '2026-01-01&select=*', undefined]) {
    assert.equal(validPriceDate(value), false);
  }
  assert.equal(validPriceDate('2024-02-29'), true);
});
test('generated graph survives a fresh handler with no local files', async () => {
  for (let build = 0; build < 2; build++) {
    const response = await priceArtifactResponse(row.date, options(Response.json([row])));
    assert.equal(response.status, 200);
    assert.match(response.headers.get('content-type'), /text\/html/);
    assert.equal(await response.text(), row.html);
  }
});
test('latest selects by date; dated query remains exact', async () => {
  for (const date of ['latest', row.date]) {
    const response = await priceArtifactResponse(date, {
      ...options(), fetchImpl: async (url, init) => {
        assert.equal(init.cache, 'no-store');
        assert.equal(url.searchParams.get(date === 'latest' ? 'order' : 'date'),
          date === 'latest' ? 'date.desc' : `eq.${date}`);
        return Response.json([row]);
      },
    });
    assert.equal(response.status, 200);
  }
});
test('missing, unavailable, corrupt and wrong-date data do not become a successful page', async () => {
  for (const [result, expected] of [
    [Response.json([]), 404], [new Response('db error', { status: 500 }), 503],
    [Response.json([{ ...row, html: 'tampered' }]), 503],
    [Response.json([{ ...row, date: '2026-09-22' }]), 503],
  ]) {
    const response = await priceArtifactResponse(row.date, options(result));
    assert.equal(response.status, expected);
    assert.equal(response.headers.get('cache-control'), 'no-store');
  }
  assert.equal((await priceArtifactResponse('invalid', options())).status, 404);
  assert.equal((await priceArtifactResponse(row.date, { url: '', key: '' })).status, 503);
});
test('immutable insert is verified by full readback; retries cannot overwrite conflicting history', async () => {
  for (const saved of [row, { ...row, html: 'other bytes' }]) {
    let calls = 0;
    const operation = publishArtifact(row, {
      ...options(), fetchImpl: async (_url, init) => {
        calls++;
        if (init.method === 'POST') {
          assert.match(init.headers.Prefer, /ignore-duplicates/);
          assert.deepEqual(JSON.parse(init.body), row);
          return new Response(null, { status: 201 });
        }
        return Response.json([saved]);
      },
    });
    if (saved === row) await operation;
    else await assert.rejects(operation, /conflict\/readback mismatch/);
    assert.equal(calls, 2);
  }
});
test('save failures stop before readback and hide response bodies', async () => {
  let calls = 0;
  await assert.rejects(publishArtifact(row, { ...options(), fetchImpl: async () => {
    calls++;
    return new Response('do not log backend details', { status: 403 });
  } }), /^Error: artifact save failed: HTTP 403$/);
  assert.equal(calls, 1);
});
