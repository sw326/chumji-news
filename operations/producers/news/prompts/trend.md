# IT 트렌드 브리핑 템플릿

## 형식

코드가 선택한 항목이 있는 섹션만 아래 순서로 출력한다. 항목 수 목표는
없으며, `articles`의 모든 항목을 정확히 한 번씩 포함한다.

```text
🔥 YYYY.MM.DD (요일) IT 트렌드 브리핑

🧭 GeekNews 큐레이션

📌 **헤드라인**
입력 근거에 명시된 내용만 요약
[GeekNews](article_url)

💬 Hacker News 커뮤니티 화제

📌 **헤드라인**
제목에서 확인되는 사실 + 관측된 점수·댓글 수
[원문](article_url) · [HN 댓글·토론](discussion_url)

🗣️ Reddit 제출

📌 **헤드라인**
제목에서 확인되는 내용만 요약
[원문](article_url) · [Reddit 댓글·토론](discussion_url)

📰 편집 뉴스 (ZDNet Korea)

📌 **헤드라인**
피드 기사 요약
[ZDNet Korea](article_url)

```

## 근거 등급별 표현 제한

- `official_metrics_title_only_no_comment_text`: `metrics`의 점수·댓글 수를
  수치로 적고 “HN에서 화제”라고 할 수 있다. 댓글 원문이 없으므로 찬반,
  우려, 호평, 열광 등 반응의 내용이나 방향은 쓰지 않는다.
- `feed_content_no_engagement`: 제목과 `summary`만 요약한다. 확산, 화제,
  열광, 반응이 많다는 표현은 쓰지 않는다.
- `title_only_no_engagement`: 제목을 번역하거나 그대로 전달하는 범위를
  넘지 않는다. URL, 도메인, 고유명을 보고 정체성·기능·산업을 추측하지
  않는다.
- 참여 지표가 없는 제목에 `viral`, `gains momentum`, `뜨거운 반응`,
  `화제` 같은 인기·확산 수식어가 들어 있어도 그 수식어는 옮기지 않고
  사건·제품·주제의 핵심 명사만 중립적으로 전달한다.

## 규칙

1. `selected=true`인 입력 항목을 모델이 추가·삭제·재선정하지 않는다.
2. 각 항목은 `source_kind`에 대응하는 섹션에 정확히 한 번 배치한다.
3. 링크는 입력의 `article_url`과 `discussion_url`만 사용한다. 홈페이지나
   섹션 URL을 새로 만들지 않는다.
4. 제목·설명은 한국어로 쓰되, 입력 근거 밖의 의미를 보충하지 않는다.
5. 출력 소스 순서는 GeekNews, Hacker News, Reddit, ZDNet Korea로 고정한다.
6. Reddit·GeekNews의 `source_kind=community_submission` 항목을 커뮤니티
   화제나 확산 사례로 바꾸지 않는다.
7. 같은 이름의 다른 항목에 설명이 있더라도 각 항목의 근거를 섞지 않는다.
8. Hacker News와 Reddit은 원문 링크와 댓글·토론 링크를 모두 표시한다.
9. 본문만 출력하고 인사말, 진행 메시지, 완료 보고를 붙이지 않는다.

