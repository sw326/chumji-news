#!/usr/bin/env node
/**
 * issue-digest.js
 * GitHub 이슈 목록을 카테고리별로 정리해서 chumji-news DB에 저장
 * AI-free: gh CLI + Supabase REST API 만 사용
 *
 * 캐싱 전략:
 *   - ~/.issue-cache.json 에 전날 이슈 스냅샷 저장
 *   - 변경사항 없으면 Supabase 저장 스킵
 *   - 텔레그램 전송용 전체 목록은 항상 출력
 */

const { execSync } = require('child_process');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');

// .env.local 로드
const envPath = path.join(__dirname, '..', '.env.local');
if (fs.existsSync(envPath)) {
  fs.readFileSync(envPath, 'utf8').split('\n').forEach(line => {
    const [k, ...v] = line.split('=');
    if (k && v.length && !process.env[k]) process.env[k] = v.join('=').trim();
  });
}

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const REPO = 'sw326/openclaw-workspace';
const CACHE_PATH = path.join(os.homedir(), '.issue-cache.json');

if (!SUPABASE_URL || !SERVICE_KEY) {
  console.error('❌ SUPABASE_URL 또는 SUPABASE_SERVICE_ROLE_KEY 없음');
  process.exit(1);
}

// 카테고리 분류 규칙
const CATS = {
  '🔥 즉시': { keywords: ['P0', '버그', 'fix:', 'hotfix', '긴급'], items: [] },
  '🚀 기능개발': { keywords: ['feat:', 'PWA', 'Samsung', 'Hi-oT', 'Spotify', 'TV', '스킬', 'skill'], items: [] },
  '🔬 리서치': { keywords: ['research:', '체험', '분석', '실험', 'MCP', 'Paper Clip', 'Claude', 'AI'], items: [] },
  '🏗️ 인프라': { keywords: ['infra:', 'Cloudflare', 'OpenClaw', 'Matrix', 'tunnel', '이관', '설정'], items: [] },
  '📚 학습': { keywords: ['스터디', 'Python', 'pandas', 'EDA', 'M0', 'M1', 'M2', 'M3', 'M4', 'ChromeOS', '강의', '수강'], items: [] },
  '📝 문서': { keywords: ['docs:', '[안녕]', '[MyAide]', '문서', '가이드'], items: [] },
  '🎮 게임': { keywords: ['게임', 'game', 'HoyoLab', '원신', '스타레일'], items: [] },
  '📦 기타': { keywords: [], items: [] },
};

function categorize(title) {
  for (const [cat, {keywords}] of Object.entries(CATS)) {
    if (cat === '📦 기타') continue;
    if (keywords.some(k => title.includes(k))) return cat;
  }
  return '📦 기타';
}

async function fetchIssues() {
  const out = execSync(
    `gh issue list -R ${REPO} --state open --limit 150 --json number,title,labels,createdAt`,
    { encoding: 'utf8' }
  );
  return JSON.parse(out);
}

function buildContent(issues, today) {
  for (const cat of Object.values(CATS)) cat.items = [];
  for (const i of issues) {
    const labels = i.labels.map(l => l.name);
    let cat;
    if (labels.includes('someday')) cat = '📚 학습';
    else if (labels.includes('GAME')) cat = '🎮 게임';
    else cat = categorize(i.title);
    CATS[cat].items.push({ num: i.number, title: i.title });
  }

  const total = issues.length;
  let md = `# 📋 이슈 다이제스트 — ${today}\n\n`;
  md += `> 총 **${total}개** 오픈 이슈 | [GitHub 보드](https://github.com/${REPO}/issues)\n\n`;
  md += '---\n\n';

  for (const [catName, {items}] of Object.entries(CATS)) {
    if (!items.length) continue;
    md += `## ${catName} (${items.length}개)\n\n`;
    for (const {num, title} of items) {
      md += `- [#${num}](https://github.com/${REPO}/issues/${num}) ${title}\n`;
    }
    md += '\n';
  }
  return md;
}

async function saveToSupabase(today, content) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({ date: today, category: 'issues', content });
    const url = new URL(`${SUPABASE_URL}/rest/v1/news_posts`);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'apikey': SERVICE_KEY,
        'Authorization': `Bearer ${SERVICE_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates',
      },
    };
    const req = https.request(options, res => {
      let data = '';
      res.on('data', d => data += d);
      res.on('end', () => res.statusCode < 300 ? resolve(data) : reject(new Error(`HTTP ${res.statusCode}: ${data}`)));
    });
    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function loadCache() {
  try {
    if (fs.existsSync(CACHE_PATH)) {
      return JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
    }
  } catch (e) {}
  return null;
}

function saveCache(date, issues) {
  const snapshot = issues.map(i => ({ number: i.number, title: i.title }));
  fs.writeFileSync(CACHE_PATH, JSON.stringify({ date, issues: snapshot }, null, 2), 'utf8');
}

function hasChanged(prevIssues, currIssues) {
  if (prevIssues.length !== currIssues.length) return true;
  const prevMap = new Map(prevIssues.map(i => [i.number, i.title]));
  for (const i of currIssues) {
    if (!prevMap.has(i.number) || prevMap.get(i.number) !== i.title) return true;
  }
  return false;
}

(async () => {
  const now = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Seoul' });
  const dateStr = now;

  console.log('이슈 목록 가져오는 중...');
  const issues = await fetchIssues();
  console.log(`총 ${issues.length}개 이슈 로드됨`);

  // 캐시 비교 → 날짜가 다르거나 이슈가 변경됐을 때 Supabase 저장
  const cache = loadCache();
  const dateChanged = !cache || cache.date !== dateStr;
  const changed = dateChanged || hasChanged(cache.issues, issues);

  if (changed) {
    const content = buildContent(issues, dateStr);
    console.log('변경사항 감지 → DB 저장 중...');
    await saveToSupabase(dateStr, content);
    console.log(`저장 완료: /news/${dateStr}/issues`);
    saveCache(dateStr, issues);
    console.log('캐시 업데이트 완료');
  } else {
    console.log('변경사항 없음 → DB 저장 스킵');
  }

  const url = `https://chumji-news.vercel.app/news/${dateStr}/issues`;
  console.log(`URL: ${url}`);
})();
