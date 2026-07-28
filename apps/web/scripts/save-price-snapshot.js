#!/usr/bin/env node
/**
 * Save the latest fresh-food price snapshot summary to chumji-news DB.
 * Stores one markdown post per date in news_posts with an opendata marker.
 */

const fs = require("fs");
const https = require("https");
const path = require("path");

const repoRoot = path.join(__dirname, "..");
const envPath = path.join(repoRoot, ".env.local");

if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, "utf8")
    .split("\n")
    .forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#")) return;
      const [key, ...value] = trimmed.split("=");
      if (key && value.length && !process.env[key]) {
        process.env[key] = value.join("=").trim();
      }
    });
}

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const DEFAULT_REPORT = path.join(
  process.env.HOME,
  ".openclaw",
  "workspace",
  "outputs",
  "fresh-food-price-alert-view",
  "report.json"
);
const PRICE_CATEGORY = "opendata";
const PRICE_PREFIX = "# 신선식품 가격 스냅샷";

function usage() {
  console.error("usage: save-price-snapshot.js [report.json]");
}

function formatDateForDb(generatedAt) {
  const match = String(generatedAt || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (match) return `${match[1]}-${match[2]}-${match[3]}`;
  return new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });
}

function formatDateLabel(value) {
  const text = String(value || "");
  if (text.length >= 8) return `${text.slice(4, 6)}/${text.slice(6, 8)}`;
  return "-";
}

function number(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function formatPrice(value) {
  const parsed = number(value);
  return parsed === null ? "-" : Math.round(parsed).toLocaleString("ko-KR");
}

function formatPct(value) {
  const parsed = number(value);
  if (parsed === null) return "n/a";
  return `${parsed > 0 ? "+" : ""}${parsed.toFixed(1)}%`;
}

function levelLabel(level) {
  if (level === "severe") return "심각";
  if (level === "alert") return "경보";
  if (level === "watch") return "관찰";
  return "정상";
}

function buildContent(report) {
  const generatedAt = String(report.generatedAt || "");
  const date = formatDateForDb(generatedAt);
  const items = Array.isArray(report.items) ? report.items : [];
  const listUrl = "https://chumji-news.vercel.app/prices";
  const detailUrl = `${listUrl}/${date}`;

  let md = `${PRICE_PREFIX} — ${date}\n\n`;
  md += `[그래프 페이지](${detailUrl}) · [가격 목록](${listUrl})\n\n`;
  md += `- 분류: 채소\n`;
  md += `- 생성 시각: ${generatedAt.replace("T", " ").replace("+09:00", " KST") || "-"}\n`;
  md += `- 기준: 가락시장 최신 도매 + KAMIS 소매 조사\n`;
  md += `- 품목: 배추 / 대파 / 양파 / 무\n\n`;

  for (const item of items) {
    const garak = item.garak && typeof item.garak === "object" ? item.garak : {};
    const kamis = item.kamis && typeof item.kamis === "object" ? item.kamis : {};
    const current = item.displayCurrent ?? garak.current ?? item.current;
    const unit = item.displayUnit || garak.unit || item.unit || "";
    const label = String(item.label || "-").replace(" / 소매", "");
    md += `## ${label}\n\n`;
    md += `- 판정: ${levelLabel(item.level)}\n`;
    md += `- 가락 현재가: ${formatPrice(current)}${unit ? ` (${unit})` : ""}\n`;
    md += `- 가락 전일 대비: ${formatPct(garak.deltaDay)}\n`;
    md += `- KAMIS 소매 1개월 대비: ${formatPct(item.deltas && item.deltas.month)}\n`;
    md += `- 기준일: 가락 ${formatDateLabel(garak.anchor)} / KAMIS ${formatDateLabel(kamis.anchor || item.anchor)}\n\n`;
  }

  if (Array.isArray(report.errors) && report.errors.length) {
    md += "## 수집 오류\n\n";
    for (const error of report.errors) {
      md += `- ${error.item || "-"}: ${error.error || "unknown"}\n`;
    }
    md += "\n";
  }

  return { date, content: md };
}

function request(method, pathname, body) {
  return new Promise((resolve, reject) => {
    const url = new URL(pathname, SUPABASE_URL);
    const payload = body ? JSON.stringify(body) : null;
    const req = https.request(
      url,
      {
        method,
        headers: {
          apikey: SERVICE_KEY,
          Authorization: `Bearer ${SERVICE_KEY}`,
          "Content-Type": "application/json",
          Prefer: "return=minimal",
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => {
          data += chunk;
        });
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(data);
          } else {
            reject(new Error(`HTTP ${res.statusCode}: ${data}`));
          }
        });
      }
    );
    req.on("error", reject);
    if (payload) req.write(payload);
    req.end();
  });
}

async function main() {
  const reportPath = process.argv[2] || DEFAULT_REPORT;
  if (process.argv.length > 3) {
    usage();
    process.exit(2);
  }
  if (!SUPABASE_URL || !SERVICE_KEY) {
    throw new Error("missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  }
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  const { date, content } = buildContent(report);
  const dateParam = encodeURIComponent(date);
  const prefixParam = encodeURIComponent(`${PRICE_PREFIX}%`);
  await request(
    "DELETE",
    `/rest/v1/news_posts?date=eq.${dateParam}&category=eq.${PRICE_CATEGORY}&content=like.${prefixParam}`
  );
  await request("POST", "/rest/v1/news_posts", {
    date,
    category: PRICE_CATEGORY,
    content,
  });
  console.log(`saved price snapshot: /prices/${date}`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
