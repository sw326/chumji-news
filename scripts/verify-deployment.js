#!/usr/bin/env node

const baseUrl = (process.argv[2] || "https://chumji-news.vercel.app").replace(/\/$/, "");

async function fetchPage(pathname) {
  const response = await fetch(`${baseUrl}${pathname}`, { redirect: "follow" });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`${pathname}: HTTP ${response.status}`);
  }
  return body;
}

async function main() {
  const requiredRoutes = ["/", "/prices", "/scraps"];
  const pages = new Map();

  for (const pathname of requiredRoutes) {
    pages.set(pathname, await fetchPage(pathname));
    console.log(`ok ${pathname}`);
  }

  if (!pages.get("/prices").includes("신선식품 가격")) {
    throw new Error("/prices: expected price page content was not found");
  }
  if (!pages.get("/scraps").includes("스크랩")) {
    throw new Error("/scraps: expected scrap page content was not found");
  }

  const detailMatch = pages.get("/").match(/href="(\/news\/\d{4}-\d{2}-\d{2}\/[a-z]+)(?:\?[^\"]*)?"/);
  if (!detailMatch) {
    throw new Error("/: no news detail route was found");
  }

  const detailPath = `${detailMatch[1]}?from=scraps`;
  const detailBody = await fetchPage(detailPath);
  if (!detailBody.includes("스크랩으로 돌아가기")) {
    throw new Error(`${detailPath}: scrap return control was not found`);
  }
  console.log(`ok ${detailPath}`);

  const newsDetailBody = await fetchPage(`${detailMatch[1]}?from=news`);
  if (!newsDetailBody.includes("뉴스 목록으로 돌아가기")) {
    throw new Error(`${detailMatch[1]}?from=news: news return control was not found`);
  }
  console.log(`ok ${detailMatch[1]}?from=news`);

  const priceMatch = pages.get("/prices").match(/href="(\/prices\/\d{4}-\d{2}-\d{2})\?from=prices"/);
  if (!priceMatch) {
    throw new Error("/prices: no price detail route was found");
  }
  const priceDetailBody = await fetchPage(`${priceMatch[1]}?from=prices`);
  if (!priceDetailBody.includes("가격 목록으로 돌아가기")) {
    throw new Error(`${priceMatch[1]}?from=prices: price return control was not found`);
  }
  console.log(`ok ${priceMatch[1]}?from=prices`);
  console.log(`verified ${baseUrl}`);
}

main().catch((error) => {
  console.error(`deployment verification failed: ${error.message}`);
  process.exit(1);
});
