---
id: source-eurostat-comext
type: source
title: Eurostat Comext
status: validated
updated_at: 2026-08-06
aliases: ["Comext", "Eurostat 무역통계"]
source_url: https://ec.europa.eu/eurostat/web/international-trade-in-goods/database
---
# Eurostat Comext

EU 국제상품무역 공식 통계 출처다. 현재 수집기는 데이터셋 `DS-045409`에서 월·신고국·상대국·HS6·수출입 방향·금액(EUR)을 조회한다.

## 현재 프로젝트의 사용 범위

- 수집기: `jobs/trade-market-briefing/eurostat_comext.py`
- 폴란드 분류: [[HS 284190]]
- 측정값: 월간 신고 수입액(EUR)
- 한계: HS6는 한국 HSK10 양극재 코드보다 넓고, 금액만으로 수량·단가·최종 수요를 분해할 수 없다.

따라서 이 출처만으로 전쟁·금리·에너지 비용·기업 재고를 원인으로 판단할 수 없다.
