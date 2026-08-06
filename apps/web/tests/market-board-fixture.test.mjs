import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const fixturePath = new URL("../src/lib/market-board-fixture.json", import.meta.url);
const fixture = JSON.parse(await readFile(fixturePath, "utf8"));

test("market fixture preserves source periods and review boundaries", () => {
  assert.equal(fixture.historical_baseline_separated, true);
  assert.ok(fixture.latest_periods.korea_customs);
  assert.ok(Array.isArray(fixture.partner_statistics));
  assert.ok(fixture.partner_statistics.length >= 4);
  assert.equal(fixture.review_gate.automated_sources_complete, true);

  for (const row of fixture.partner_statistics) {
    if (!row.mirror_comparable) assert.equal(row.mirror_gap_usd, null);
    assert.ok(Array.isArray(row.quality.limitations));
  }
});

test("market fixture exposes monthly series without mixing currency or classification", () => {
  assert.ok(Array.isArray(fixture.time_series));
  assert.deepEqual(
    fixture.time_series.map((series) => series.country_code),
    ["KR", "US", "HU", "PL"],
  );
  for (const series of fixture.time_series) {
    assert.ok(series.currency);
    assert.ok(series.classification);
    assert.ok(series.points.length >= 5);
    for (const point of series.points) {
      assert.match(point.period, /^\d{4}-\d{2}$/);
      assert.equal(point.previous_period.slice(5), point.period.slice(5));
    }
  }
});
