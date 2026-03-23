# TODOS

## chumji-news 웹앱

### 초기 세팅 + 전체 구현
**What:** chumji-news 뉴스 보드 웹앱 전체 구현.
**Why:** 매일 크론 뉴스 브리핑을 채팅 대신 보기 좋은 웹 UI로 제공. Telegram은 링크만 전송.
**Context:** 
- 이슈: sw326/openclaw-workspace#114
- 라우팅: `/` (메인 리스트) + `/news/[date]/[cat]` (경량 단일 뉴스 페이지)
- 메인: 날짜별 카드, 탭(전체/뉴스/IT/트렌드/강남3구), FAB, 반응형
- 단일 페이지: 초경량, 탭 없음, 텔레그램 링크 타겟
- 스택: Next.js 15 + Tailwind v4 + Supabase + Vercel
- DB 스키마: news_posts(id, date, category, content, created_at)
- 카테고리: news / it / trend / realestate
- 반응형: 데스크탑(좌우 분할) / 태블릿 이하(상하)
- FAB: 최상단 버튼 1개
**Effort:** L
**Priority:** P0
**Depends on:** Supabase 프로젝트 생성 (수동 필요 — 완료 후 .env.local에 URL+키 제공)

### 크론 수정 (별도 작업)
**What:** 기존 뉴스 크론 4개를 Supabase 저장 + Telegram 링크 전송으로 수정.
**Why:** 현재 Telegram에 전문 전송 → 링크만 전송으로 전환.
**Context:**
- 대상: 📰뉴스(08:00) / 💻IT(13:00) / 🔥트렌드(18:00) / 🏠강남3구(월10:00)
- Supabase insert 후 → `https://chumji-news.vercel.app/news/[date]/[cat]` 링크 전송
- Supabase 키는 ~/.config/supabase/ 에 저장 예정
**Effort:** M
**Priority:** P1
**Depends on:** 웹앱 구현 완료 + Supabase 세팅

## Completed
