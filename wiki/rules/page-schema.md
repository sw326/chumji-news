---
id: rule-page-schema
type: rule
title: 페이지 스키마
status: verified
updated_at: 2026-08-06
aliases: ["Wiki page schema"]
---
# 페이지 스키마

모든 관리 페이지는 `id`, `type`, `title`, `status`, `updated_at`, `aliases`를 갖는다. 상태는 다음 의미로 쓴다.

- `verified`: 원자료 또는 재현 가능한 계산으로 확인
- `review`: 관측됐으나 범위·해석 검토가 필요
- `hypothesis`: 검증 전 가설
- `draft`: 구조·내용 작성 중

출처 페이지에는 가능한 경우 `source_url`을 둔다. 문서 링크는 Obsidian의 이중 대괄호 형식으로 제목 또는 별칭을 지정한다. 자동 생성 인덱스는 직접 수정하지 않는다.
