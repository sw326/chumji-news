import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";

const page = await readFile(new URL("../src/app/market/page.tsx", import.meta.url), "utf8");
const loader = await readFile(new URL("../src/lib/market-board-data.ts", import.meta.url), "utf8");

test("market page exposes remote and fallback provenance", () => {
  assert.match(loader, /MARKET_BOARD_FORCE_FALLBACK/);
  assert.match(page, /실시간 검증본/);
  assert.match(page, /내장 검증본 사용 중/);
  assert.match(page, /마지막 검증본을 표시합니다/);
});

test("market page translates the pending GACC review state", () => {
  assert.match(loader, /MARKET_BOARD_REHEARSAL_GACC_PENDING/);
  assert.match(page, /pending-one-time-verification/);
  assert.match(page, /수동 검증 대기/);
  assert.match(page, /중국 GACC 수동 검수/);
});

test("market page keeps separate mobile cards and desktop table", () => {
  assert.match(page, /md:hidden/);
  assert.match(page, /hidden overflow-x-auto md:block/);
});
