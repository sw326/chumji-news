import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = (path) => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("the surviving navigation exposes only finished news product routes", async () => {
  const tabs = await source("src/components/MainTabs.tsx");

  for (const label of ["뉴스", "가격", "스크랩"]) assert.match(tabs, new RegExp(`label="${label}"`));
  for (const route of ["/market", "/alerts", "/operations"]) assert.doesNotMatch(tabs, new RegExp(route));
  assert.match(tabs, /min-h-10/);
});

test("bookmarks keep a complete index and serialize writes per article", async () => {
  const [provider, migration] = await Promise.all([
    source("src/components/ScrapProvider.tsx"),
    source("supabase/migrations/003_create_news_scraps.sql"),
  ]);

  assert.match(provider, /select\("id, article_key"\)/);
  assert.match(provider, /pendingArticleKeysRef\.current\.has/);
  assert.match(provider, /isScrapPending/);
  assert.match(provider, /SCRAPS_PAGE_SIZE/);
  assert.match(migration, /UNIQUE \(user_id, article_key\)/);
});

test("bookmark management retains search, filters, sorting, undo, and OTP cooldown", async () => {
  const scraps = await source("src/app/scraps/page.tsx");

  assert.match(scraps, /type="search"/);
  assert.match(scraps, /category === "all"/);
  assert.match(scraps, /sort === "newest"/);
  assert.match(scraps, /handleUndo/);
  assert.match(scraps, /OTP_COOLDOWN_KEY/);
  assert.match(scraps, /isScrapPending/);
});

test("news detail cards expose guarded bookmark controls while price pages stay separate", async () => {
  const [page, renderer, prices, priceDetail] = await Promise.all([
    source("src/app/news/[date]/[cat]/page.tsx"),
    source("src/components/MarkdownRenderer.tsx"),
    source("src/app/prices/page.tsx"),
    source("src/app/prices/[date]/page.tsx"),
  ]);

  assert.match(page, /postId=\{post\.id\}/);
  assert.match(renderer, /aria-label=\{pending \? "북마크 변경 중"/);
  assert.match(renderer, /disabled=\{pending\}/);
  assert.doesNotMatch(prices, /ScrapProvider|useScraps|기사 북마크/);
  assert.doesNotMatch(priceDetail, /ScrapProvider|useScraps|기사 북마크/);
});
