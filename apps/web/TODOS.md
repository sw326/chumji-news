# chumji-news TODOS

## P0 — UI 전면 개편 + 카테고리 확장

### What
1. **카테고리 7개로 확장** (현재 4개)
   - 기존: `news` / `it` / `trend` / `realestate`
   - 추가: `moltbook` / `opendata` / `system`
   - `src/lib/types.ts` Category 타입, CATEGORY_LABELS, CATEGORIES 배열 업데이트

2. **뉴스 상세 페이지 (`/news/[date]/[cat]`) UI 전면 개편**
   - 현재: 마크다운 텍스트 dump, 링크 처리 없음, 가로 스크롤 발생
   - 목표: 기사별 카드 UI, 링크 처리, 반응형

   **콘텐츠 파싱 전략** (content 구조 패턴):
   ```
   # 헤더 (브리핑 제목)
   
   ## 섹션 헤더 (🌍 해외 / 📰 보수 언론 / 💻 IT 등)
   
   🇺🇸 **기사 제목**
   기사 설명 텍스트
   [출처명](https://실제URL)
   
   ---
   
   📈 증시 / 🔥 핫이슈 등 블록
   ```

   - **섹션 단위로 그룹핑**: `##` 헤더 기준으로 섹션 분리
   - **기사 블록 파싱**: 이모지 + `**굵은제목**` + 설명 + `[출처](URL)` 패턴 감지
   - **기사 카드**: 제목 / 한 줄 설명 / 출처 링크 버튼 (external tab) 으로 구성
   - **링크**: `[text](url)` → `<a href="url" target="_blank" rel="noopener">text</a>`
   - **증시/핫이슈/프로모션 블록**: 카드와 구분되는 별도 스타일 섹션으로 렌더링
   - **반응형**: `max-w-2xl`, `overflow-x: hidden`, `word-break: break-word`

3. **메인 리스트 페이지 (`/`) 카드 개선**
   - 현재: 제목만 있음
   - 목표: 카테고리 배지 + 날짜 + 핵심 헤드라인 2~3줄 preview

### Why
- 텔레그램 링크 클릭 → 웹앱 진입 → 가독성 좋은 뷰가 핵심 가치
- 현재 UI는 텍스트 dump 수준, 링크도 동작 안 해서 의미 없음

### Context
- 프레임워크: Next.js 15 + Tailwind v4 (CSS 변수 기반 커스텀 테마)
- 기존 컴포넌트: `MarkdownRenderer.tsx` (자체 파서), `NewsCard.tsx`, `NewsBoardClient.tsx`, `CategoryTabs.tsx`
- globals.css에 `.prose` 클래스 스타일 정의됨
- 다크모드 지원 (`prefers-color-scheme: dark`)
- `react-markdown` 등 외부 라이브러리 추가 가능 (npm install)

### Effort: L (반나절)
### Priority: P0

---

## P1 — Supabase category 제약 업데이트

### What
Supabase Dashboard SQL Editor에서 아래 SQL 실행 (첨지 직접):
```sql
ALTER TABLE news_posts DROP CONSTRAINT news_posts_category_check;
ALTER TABLE news_posts ADD CONSTRAINT news_posts_category_check 
  CHECK (category IN ('news', 'it', 'trend', 'realestate', 'moltbook', 'opendata', 'system'));
```

### Why
크론에서 새 카테고리로 insert 시 constraint 오류 방지

### Effort: XS
### Priority: P1 (Claude Code 작업 전에 첨지가 먼저 실행)

---

## Done
- [x] Next.js 15 앱 초기 구현
- [x] Vercel 배포 (`https://chumji-news.vercel.app`)
- [x] Supabase `news_posts` 테이블 생성
- [x] 크론 4개 Supabase insert 연동 (news/it/trend/realestate)
- [x] Cross-Context 텔레그램 전송 버그 수정
- [x] Vercel 환경변수 설정 + 재배포
