#!/usr/bin/env python3
"""Build a freshness-aware cathode-material market board from official sources."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

from analysis_metrics import compare_period_rows, market_structure
from battery_classification import summarize_trade_precision
from customs_trade_compare import aggregate, fetch_country
from customs_trade_compare import DEFAULT_KEY_FILE, load_api_key
from eurostat_comext import fetch_comext_value
from gacc_snapshot import load_gacc_period_snapshot
from supply_chain_map import fetch_us_imports


CATHODE_HSK = (
    "2825902050", "2841909010", "2841909020",
    "2841909030", "2842909000", "3824999090",
)
DEFAULT_PARTNERS = ("US", "CN", "HU", "PL")
HS6_CODES = tuple(dict.fromkeys(code[:6] for code in CATHODE_HSK))


def shift_month(period: str, offset: int) -> str:
    index = int(period[:4]) * 12 + int(period[4:]) - 1 + offset
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def latest_published_month(
    api_key: str,
    *,
    fetcher: Callable[..., list[dict[str, Any]]] = fetch_country,
    today: date | None = None,
    probe_countries: tuple[str, ...] = DEFAULT_PARTNERS,
    probe_codes: tuple[str, ...] = CATHODE_HSK,
    lookback_months: int = 14,
) -> dict[str, Any]:
    """Find the newest month evidenced by a non-total row, never by an empty response."""
    current = (today or date.today()).strftime("%Y%m")
    checked: list[str] = []
    errors: dict[str, str] = {}
    for offset in range(lookback_months):
        period = shift_month(current, -offset)
        checked.append(period)
        for country in probe_countries:
            for code in probe_codes:
                try:
                    rows = fetcher(api_key, country, period, period, code, 20.0)
                except RuntimeError as exc:
                    errors[f"{period}:{country}:{code}"] = str(exc)
                    continue
                if any(
                    str(row.get("hsCd", "")) not in {"", "-"}
                    and str(row.get("year", "")).replace(".", "")[:6] == period
                    for row in rows
                ):
                    return {
                        "period": period,
                        "checked_periods": checked,
                        "evidence": {"country": country, "hsk10": code},
                        "errors": errors,
                    }
    raise RuntimeError(f"최근 {lookback_months}개월에서 관세청 공개 월을 확인하지 못했습니다.")


def collect_korea_cumulative(
    api_key: str,
    latest_period: str,
    *,
    countries: tuple[str, ...] = DEFAULT_PARTNERS,
    codes: tuple[str, ...] = CATHODE_HSK,
    fetcher: Callable[..., list[dict[str, Any]]] = fetch_country,
) -> dict[str, Any]:
    start = latest_period[:4] + "01"
    previous_start = str(int(latest_period[:4]) - 1) + "01"
    previous_end = str(int(latest_period[:4]) - 1) + latest_period[4:]
    buckets: dict[str, list[dict[str, Any]]] = {"current": [], "previous": []}
    errors: dict[str, str] = {}
    for label, begin, end in (
        ("current", start, latest_period),
        ("previous", previous_start, previous_end),
    ):
        for country in countries:
            for code in codes:
                try:
                    buckets[label].extend(fetcher(api_key, country, begin, end, code, 20.0))
                except RuntimeError as exc:
                    errors[f"{label}:{country}:{code}"] = str(exc)
    current_rows, previous_rows = aggregate(buckets["current"]), aggregate(buckets["previous"])
    comparison = compare_period_rows(
        current_rows, previous_rows, value_key="export_usd",
        identity_keys=("country_code", "hs_code"),
    )
    return {
        "period": {"start": start, "end": latest_period, "previous_start": previous_start, "previous_end": previous_end},
        "rows": current_rows,
        "previous_rows": previous_rows,
        "totals": {
            "export_usd": sum(float(row.get("export_usd", 0) or 0) for row in current_rows),
            "previous_export_usd": sum(float(row.get("export_usd", 0) or 0) for row in previous_rows),
        },
        "period_comparison": comparison,
        "classification_precision": summarize_trade_precision(current_rows, "export_usd"),
        "market_structure": market_structure(
            current_rows, value_key="export_usd", country_key="country_code", weight_key="export_kg"
        ),
        "errors": errors,
        "partial": bool(errors) and bool(current_rows),
        "source": {
            "name": "관세청 품목별 국가별 수출입실적",
            "quality_score": 95,
            "quality_grade": "high",
            "classification": "HSK10 2026",
            "freshness": "latest-published-month",
            "basis": "수출 FOB",
        },
    }


def collect_us_cumulative(
    latest_period: str,
    *,
    hs6_codes: tuple[str, ...] = HS6_CODES,
    fetcher: Callable[..., list[dict[str, Any]]] = fetch_us_imports,
) -> dict[str, Any]:
    """Collect US imports from Korea using Census year-to-date fields."""
    iso_period = latest_period[:4] + "-" + latest_period[4:]
    previous_period = str(int(latest_period[:4]) - 1) + "-" + latest_period[4:]
    current_rows, previous_rows, errors = [], [], {}
    for label, period, destination in (
        ("current", iso_period, current_rows), ("previous", previous_period, previous_rows)
    ):
        for code in hs6_codes:
            try:
                destination.extend(fetcher(period, "5800", code))
            except RuntimeError as exc:
                errors[f"{label}:{code}"] = str(exc)
    current = sum(float(row.get("GEN_VAL_YR", 0) or 0) for row in current_rows)
    previous = sum(float(row.get("GEN_VAL_YR", 0) or 0) for row in previous_rows)
    return {
        "country_code": "US", "period": iso_period,
        "previous_period": previous_period, "value": current, "previous_value": previous,
        "growth_rate": current / previous - 1 if previous else None,
        "currency": "USD", "classification": "HS6",
        "data_status": "available" if current_rows else "no-reported-rows",
        "quality": {"score": 80, "maximum": 100, "grade": "high", "limitations": ["한국 HSK10보다 넓은 HS6"]},
        "errors": errors, "source": "US Census International Trade API",
    }


def _eurostat_latest_period(result: dict[str, Any]) -> str | None:
    periods = [str(row.get("period", "")) for row in result.get("observations", []) if row.get("period")]
    return max(periods, default=None)


def collect_eu_cumulative(
    country: str,
    requested_year: str,
    *,
    hs6_codes: tuple[str, ...] = HS6_CODES,
    fetcher: Callable[..., dict[str, Any]] = fetch_comext_value,
) -> dict[str, Any]:
    """Collect latest common Comext YTD imports from Korea and world exports."""
    imports, exports, errors = [], [], {}
    for code in hs6_codes:
        for flow, partner, destination in (("M", "KR", imports), ("X", "WORLD", exports)):
            try:
                destination.append((code, fetcher(country, partner, code, requested_year, flow)))
            except RuntimeError as exc:
                errors[f"{flow}:{code}"] = str(exc)
    # A code can legitimately have no trade in the newest month.  The newest
    # period evidenced anywhere in the same Comext dataset is the publication
    # cutoff; taking the minimum would mistake sparse trade for publication lag.
    periods = [p for _, result in imports + exports if (p := _eurostat_latest_period(result))]
    latest = max(periods) if periods else None
    previous_year = str(int(requested_year) - 1)
    previous_imports, previous_errors = [], {}
    if latest:
        for code in hs6_codes:
            try:
                previous_imports.append((code, fetcher(country, "KR", code, previous_year, "M")))
            except RuntimeError as exc:
                previous_errors[code] = str(exc)
    month = latest[5:] if latest else ""
    def total_through(rows: list[tuple[str, dict[str, Any]]], year: str, end_month: str) -> float:
        cutoff = f"{year}-{end_month}"
        return sum(
            float(obs.get("value", 0) or 0)
            for _, result in rows for obs in result.get("observations", [])
            if str(obs.get("period", "")) <= cutoff
        )
    imports_value = total_through(imports, requested_year, month) if latest else 0.0
    exports_value = total_through(exports, requested_year, month) if latest else 0.0
    previous_value = total_through(previous_imports, previous_year, month) if latest else 0.0
    ratio = exports_value / imports_value if imports_value else None
    signal = "unknown" if ratio is None else "high" if ratio >= .5 else "medium" if ratio >= .1 else "low"
    return {
        "country_code": country, "period": latest, "previous_period": f"{previous_year}-{month}" if latest else None,
        "value": imports_value, "previous_value": previous_value,
        "growth_rate": imports_value / previous_value - 1 if previous_value else None,
        "world_export_value": exports_value, "world_export_to_import_ratio": ratio,
        "reexport_signal": signal, "currency": "EUR", "classification": "HS6",
        "data_status": "available" if latest else "no-reported-rows",
        "quality": {"score": 75 if latest else 25, "maximum": 100, "grade": "medium" if latest else "low", "limitations": ["한국 HSK10보다 넓은 HS6", "EUR이므로 한국 USD 신고액과 직접 차액 비교 불가"]},
        "errors": {**errors, **{f"previous:{k}": v for k, v in previous_errors.items()}},
        "source": "Eurostat Comext",
    }


def assemble_market_board(korea: dict[str, Any], partners: list[dict[str, Any]], *, as_of: str) -> dict[str, Any]:
    korea_end = korea["period"]["end"][:4] + "-" + korea["period"]["end"][4:]
    korea_by_country: dict[str, float] = {}
    for row in korea.get("rows", []):
        country = str(row.get("country_code", ""))
        korea_by_country[country] = korea_by_country.get(country, 0.0) + float(row.get("export_usd", 0) or 0)
    comparisons = []
    for item in partners:
        same_period = item.get("period") == korea_end
        comparable_currency = item.get("currency") == "USD"
        korean_value = korea_by_country.get(str(item.get("country_code")), 0.0)
        partner_value = float(item.get("value", 0) or 0)
        comparable_scope = bool(item.get("scope_comparable", True))
        comparable = same_period and comparable_currency and comparable_scope
        comparisons.append({
            **item, "korea_reported_export_usd": korean_value,
            "period_alignment": "same-period" if same_period else "different-period",
            "mirror_comparable": comparable,
            "mirror_gap_usd": partner_value - korean_value if comparable else None,
            "comparison_notice": (
                "동일 누계기간·USD 기준 비교 가능" if comparable else
                "기간·통화 또는 코드 범위가 달라 직접 차액 비교 불가"
            ),
        })
    return {
        "title": "양극재 최신 시장판", "as_of": as_of,
        "latest_periods": {"korea_customs": korea_end, **{item["country_code"]: item.get("period") for item in partners}},
        "historical_baseline_separated": True,
        "korea": korea, "partner_statistics": comparisons,
        "aggregation_policy": "국가·출처별 최신 공개 월이 다르면 합산하지 않는다.",
    }


def build_review_gate(board: dict[str, Any]) -> dict[str, Any]:
    precision = board["korea"]["classification_precision"]
    total = float(precision.get("total_value_usd", 0) or 0)
    broad_share = float(precision.get("broad_value_usd", 0) or 0) / total if total else 0.0
    partner_rows = board.get("partner_statistics", [])
    blockers, warnings = [], []
    if not board["korea"].get("rows"):
        blockers.append("한국 관세청 최신 누계 행이 없습니다.")
    if broad_share >= .2:
        blockers.append("기타·광범위 코드 비중이 20% 이상이라 전체 금액을 양극재로 귀속할 수 없습니다.")
    missing = [
        row["country_code"] for row in partner_rows
        if row.get("country_code") != "CN" and row.get("data_status") != "available"
    ]
    if missing:
        blockers.append("상대국 공식 통계 누락: " + ", ".join(missing))
    if any(not row.get("mirror_comparable") for row in partner_rows):
        warnings.append("기간 또는 통화가 다른 상대국은 거울통계 차액을 계산하지 않았습니다.")
    warnings.extend([
        "HS6 상대국 통계에는 한국 HSK10 선택 범위 밖 품목이 포함됩니다.",
        "재수출 가능성은 세계 수출/한국산 수입 비율에 따른 탐색 신호이며 실제 재수출액이 아닙니다.",
    ])
    china = next((row for row in partner_rows if row.get("country_code") == "CN"), None)
    return {
        "status": "blocked" if blockers else "review-required",
        "automated_sources_complete": not missing and bool(board["korea"].get("rows")),
        "china_manual_check": {
            "status": "verified" if china and china.get("data_status") == "available" else "pending-one-time-verification",
            "target_period": board["latest_periods"].get("korea_customs"),
            "instruction": (
                "GACC 공식 화면에서 2026년 1~6월 누계를 수동 검증함"
                if china and china.get("data_status") == "available" else
                "한국·미국·EU 기준월 확정 후 GACC 공식 화면에서 동일 또는 가장 가까운 공개 월을 한 번만 검증"
            ),
        },
        "blockers": blockers, "warnings": warnings,
    }


def build_live_board(api_key: str, *, today: date | None = None) -> dict[str, Any]:
    current_date = today or date.today()
    latest = latest_published_month(api_key, today=current_date)
    korea = collect_korea_cumulative(api_key, latest["period"])
    us = collect_us_cumulative(latest["period"])
    eu = [collect_eu_cumulative(country, latest["period"][:4]) for country in ("HU", "PL")]
    gacc = load_gacc_period_snapshot("28419000", latest["period"][:4], "first-half")
    china = {
        "country_code": "CN", "period": latest["period"][:4] + "-" + latest["period"][4:],
        "previous_period": None, "value": float(gacc.get("value", 0) or 0) if gacc else 0.0,
        "previous_value": None, "growth_rate": None, "currency": "USD", "classification": "HS8",
        "data_status": "available" if gacc else "not-manually-verified",
        "quality": {"score": 65 if gacc else 20, "maximum": 100, "grade": "medium" if gacc else "insufficient", "limitations": ["중국 HS8 28419000은 한국 양극재 HSK10보다 넓음", "다른 광범위 HS8 후보는 이번 최신월 검증 범위에서 제외"]},
        "errors": {}, "source": "China GACC official interactive table",
        "quantity_kg": float(gacc.get("quantity", 0) or 0) if gacc else None,
        "captured_at": gacc.get("captured_at") if gacc else None,
        "scope_warning": gacc.get("scope_warning") if gacc else None,
        "scope_comparable": False,
    }
    board = assemble_market_board(korea, [us, *eu, china], as_of=current_date.isoformat())
    board["latest_detection"] = latest
    board["review_gate"] = build_review_gate(board)
    return board


def render_market_board(board: dict[str, Any]) -> str:
    """Render a dependency-free static review artifact with embedded data."""
    payload = json.dumps(board, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>양극재 최신 시장판</title><style>
:root{{--ink:#17202a;--muted:#667085;--line:#d9e0e8;--bg:#f4f7fa;--card:#fff;--blue:#2457d6;--warn:#9a6700}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,-apple-system,sans-serif}}
main{{max-width:1180px;margin:auto;padding:36px 20px}}h1{{margin:0 0 4px}}h2{{margin-top:32px}}.muted{{color:var(--muted)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}
.metric{{font-size:25px;font-weight:750}}.tag{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:2px 9px;margin:2px;font-size:12px}}
table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:11px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{color:var(--muted);font-size:12px}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.warn{{color:var(--warn)}}
@media(max-width:700px){{.table{{overflow:auto}}table{{min-width:820px}}}}
</style></head><body><main><h1>양극재 최신 시장판</h1><p class="muted" id="asof"></p><div id="app"></div>
<script id="market-data" type="application/json">{payload}</script><script>
const d=JSON.parse(document.getElementById('market-data').textContent), fmt=(v,c='USD')=>new Intl.NumberFormat('ko-KR',{{style:'currency',currency:c,maximumFractionDigits:0}}).format(v||0), pct=v=>v==null?'비교 불가':(v*100).toFixed(1)+'%';
document.getElementById('asof').textContent=`조회일 ${{d.as_of}} · 국가·출처별 공개월이 다르면 합산하지 않습니다.`;
const k=d.korea,p=k.classification_precision,g=d.review_gate, periods=Object.entries(d.latest_periods).map(([a,b])=>`<span class="tag">${{a}} ${{b}}</span>`).join('');
let h=`<div class="grid"><div class="card"><div class="muted">한국 최신 누계 수출</div><div class="metric">${{fmt(k.totals.export_usd)}}</div><div>${{k.period.start}}–${{k.period.end}}</div></div><div class="card"><div class="muted">전년동기 증감</div><div class="metric">${{pct(k.period_comparison.growth_rate)}}</div><div>${{fmt(k.period_comparison.change_usd)}}</div></div><div class="card"><div class="muted">전용 품명 코드 비중</div><div class="metric">${{pct(p.dedicated_share)}}</div><div class="warn">광범위 코드 ${{fmt(p.broad_value_usd)}}</div></div><div class="card"><div class="muted">검수 게이트</div><div class="metric">${{g.status}}</div><div>자동 출처 ${{g.automated_sources_complete?'완료':'미완료'}}</div></div></div><h2>데이터 기준일</h2><div class="card">${{periods}}</div><h2>상대국 공식 통계</h2><div class="table"><table><thead><tr><th>국가·출처</th><th>기준월</th><th class="num">한국산 수입</th><th>전년동기</th><th>한국 신고와 차이</th><th>품질</th><th>재수출 신호</th></tr></thead><tbody>`;
h+=d.partner_statistics.map(x=>`<tr><td><strong>${{x.country_code}}</strong><div class="muted">${{x.source}}</div></td><td>${{x.period}}</td><td class="num">${{fmt(x.value,x.currency)}}</td><td>${{pct(x.growth_rate)}}</td><td>${{x.mirror_comparable?fmt(x.mirror_gap_usd):'<span class="warn">비교 불가</span>'}}<div class="muted">${{x.comparison_notice}}</div></td><td>${{x.quality.score}}/${{x.quality.maximum}} · ${{x.quality.grade}}<div class="muted">${{x.quality.limitations.join(', ')}}</div></td><td>${{x.reexport_signal||'산출 안 함'}}</td></tr>`).join('');
h+=`</tbody></table></div><h2>검수 결과</h2><div class="card"><strong>중국 GACC: ${{g.china_manual_check.status}}</strong><p>${{g.china_manual_check.instruction}} · 대상 기준월 ${{g.china_manual_check.target_period}}</p><ul>${{g.warnings.map(x=>`<li>${{x}}</li>`).join('')}}</ul></div>`;document.getElementById('app').innerHTML=h;
</script></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description="양극재 최신 공식통계 시장판 생성")
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--output", type=Path, default=Path("output/cathode-current-market.json"))
    parser.add_argument("--html-output", type=Path, default=Path("deploy/cathode-current.html"))
    args = parser.parse_args()
    board = build_live_board(load_api_key(args.key_file))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(board, ensure_ascii=False, indent=2), encoding="utf-8")
    args.html_output.parent.mkdir(parents=True, exist_ok=True)
    args.html_output.write_text(render_market_board(board), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output), "html_output": str(args.html_output), "latest_periods": board["latest_periods"],
        "review_gate": board["review_gate"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
