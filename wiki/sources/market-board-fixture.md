---
id: source-market-board-fixture
type: source
title: 양극재 시장판 검증 픽스처
status: verified
updated_at: 2026-08-06
aliases: ["market-board-fixture.json"]
source_url: repo:apps/web/src/lib/market-board-fixture.json
---
# 양극재 시장판 검증 픽스처

현재 운영 화면의 검증된 정적 기준본이다. 저장 위치는 `apps/web/src/lib/market-board-fixture.json`이며, 폴란드 신호에는 같은 출처·월·통화·분류의 전년 동월 비교가 들어 있다.

이 파일은 분석의 최종 원자료가 아니라 [[Eurostat Comext]] 수집 결과를 정규화한 검증 산출물이다. 계산 재현 시 원 API와 수집기를 함께 확인해야 한다.
