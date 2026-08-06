import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path) => readFile(new URL(`../src/${path}`, import.meta.url), "utf8");

test("all news detail categories receive article scrap controls", async () => {
  const [page, renderer, types] = await Promise.all([
    source("app/news/[date]/[cat]/page.tsx"),
    source("components/MarkdownRenderer.tsx"),
    source("lib/types.ts"),
  ]);

  assert.match(page, /postId=\{post\.id\}/);
  assert.match(page, /category=\{post\.category\}/);
  assert.match(renderer, /aria-label=\{saved \? "스크랩 해제" : "기사 스크랩"\}/);
  for (const category of ["news", "it", "trend", "realestate", "moltbook", "opendata", "system", "issues", "reddit"]) {
    assert.match(types, new RegExp(`"${category}"`));
  }
});

test("price pages remain outside the news scrap flow", async () => {
  const [prices, priceDetail] = await Promise.all([
    source("app/prices/page.tsx"),
    source("app/prices/[date]/page.tsx"),
  ]);

  assert.doesNotMatch(prices, /ScrapProvider|useScraps|기사 스크랩/);
  assert.doesNotMatch(priceDetail, /ScrapProvider|useScraps|기사 스크랩/);
});
