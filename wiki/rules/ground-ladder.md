---
id: rule-ground-ladder
type: rule
title: GROUND 읽기 사다리
status: verified
updated_at: 2026-08-06
aliases: ["GROUND Ladder"]
---
# GROUND 읽기 사다리

- R0: 연구 질문에 직접 연결된 근거와 출처를 읽는다.
- R1: 국가·산업·지표 인덱스에서 누락된 주제를 찾는다.
- R2: 정방향 링크와 역링크를 1~2홉 순회한다.
- R3: 파일명·별칭·전문 검색으로 아직 연결되지 않은 문서를 찾는다.
- R4: 근거가 계속 부족할 때만 관련 클러스터의 범위를 넓힌다.

근거 없는 주장, 링크 단절, 경쟁 가설 미식별, 상충 수치, 중복 엔티티 가능성이 있을 때 다음 단계로 올라간다. 답변에는 도달 단계와 남은 증거 격차를 표시한다.

이 규칙은 Karpathy의 LLM Wiki 계층 아이디어와 `alfadur7/llm-wiki-newsroom`의 공개 설계에서 영감을 얻었지만, 외부 코드·예제 콘텐츠·분류 체계는 복사하지 않았다.
