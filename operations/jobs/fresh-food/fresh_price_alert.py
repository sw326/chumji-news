#!/usr/bin/env python3
"""Fresh-food price alert CLI for aT/KAMIS public-data APIs.

Uses recent/price as code discovery and anchor date, then combines daily and
monthly APIs. Garak Market integration is intentionally left as a separate
source adapter so credentials stay outside this script.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

ENDPOINTS = {
    "recent": "https://apis.data.go.kr/B552845/recent/price",
    "per_day": "https://apis.data.go.kr/B552845/perDay/price",
    "per_region": "https://apis.data.go.kr/B552845/perRegion/price",
    "per_year_month": "https://apis.data.go.kr/B552845/perYearMonth/price",
}

DEFAULT_KEY_FILE = pathlib.Path(
    os.getenv(
        "DATA_GO_KR_KEY_FILE",
        str(pathlib.Path.home() / ".config" / "data-go-kr" / "api_key"),
    )
)
REQUEST_TIMEOUT_SECONDS = float(os.getenv("FRESH_PRICE_REQUEST_TIMEOUT", "12"))
REQUEST_ATTEMPTS = max(1, int(os.getenv("FRESH_PRICE_REQUEST_ATTEMPTS", "2")))


def read_key() -> str:
    key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    if key:
        return key
    if DEFAULT_KEY_FILE.exists():
        return DEFAULT_KEY_FILE.read_text().strip()
    raise SystemExit("DATA_GO_KR_SERVICE_KEY is missing and ~/.config/data-go-kr/api_key was not found")


def parse_ymd(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y%m%d").date()


def ymd(value: dt.date) -> str:
    return value.strftime("%Y%m%d")


def ym(value: dt.date) -> str:
    return value.strftime("%Y%m")


def add_months(value: dt.date, months: int) -> dt.date:
    month = value.month + months
    year = value.year
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return value.replace(year=year, month=month, day=1)


def request_json(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params, doseq=True, safe="[]:")
    req = urllib.request.Request(
        f"{endpoint}?{query}",
        headers={"User-Agent": "openclaw-fresh-food-price-alert/0.2"},
    )
    raw = ""
    for attempt in range(1, REQUEST_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            break
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt >= REQUEST_ATTEMPTS:
                raise RuntimeError(
                    f"data.go.kr unavailable after {REQUEST_ATTEMPTS} attempts: {exc}"
                ) from exc
            time.sleep(min(2 ** (attempt - 1), 2))
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


def body(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    return payload.get("body") or payload.get("response", {}).get("body") or {}


def extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    b = body(payload)
    items = b.get("items")
    if isinstance(items, dict):
        items = items.get("item")
    if items in (None, [], ""):
        return []
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return [row for row in items if isinstance(row, dict)]
    return []


def common_params(key: str, rows: int = 1000) -> dict[str, str]:
    return {"serviceKey": key, "pageNo": "1", "numOfRows": str(rows), "returnType": "JSON"}


def number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def row_price(row: dict[str, Any]) -> float | None:
    for key in ("exmn_dd_cnvs_prc", "exmn_dd_prc", "exmn_avrg_kg_cnvrsn_prc", "exmn_avrg_prc", "pmm_avgprc"):
        found = number(row.get(key))
        if found is not None:
            return found
    return None


def filter_recent(rows: Iterable[dict[str, Any]], item: str, variety: str | None, grade: str | None, side: str | None) -> list[dict[str, Any]]:
    matches = []
    for row in rows:
        names = [str(row.get("item_nm", "")), str(row.get("vrty_nm", ""))]
        if item and not (row.get("item_nm") == item or any(item in name for name in names)):
            continue
        if variety and variety not in str(row.get("vrty_nm", "")):
            continue
        if grade and grade not in str(row.get("grd_nm", "")):
            continue
        if side and side not in str(row.get("se_nm", "")):
            continue
        matches.append(row)
    return matches


def choose_recent(rows: list[dict[str, Any]], prefer_side: str, item: str) -> dict[str, Any] | None:
    def sort_key(row: dict[str, Any]) -> tuple[int, str, int]:
        exact_item_score = 1 if str(row.get("item_nm", "")) == item else 0
        side_score = 1 if prefer_side in str(row.get("se_nm", "")) else 0
        date = str(row.get("exmn_ymd", ""))
        grade_score = 1 if str(row.get("grd_nm", "")) == "상품" else 0
        return exact_item_score, side_score, date, grade_score
    return max(rows, key=sort_key) if rows else None


def code_filters(row: dict[str, Any]) -> dict[str, str]:
    mapping = {
        "ctgry_cd": "cond[ctgry_cd::EQ]",
        "item_cd": "cond[item_cd::EQ]",
        "vrty_cd": "cond[vrty_cd::EQ]",
        "grd_cd": "cond[grd_cd::EQ]",
    }
    out = {}
    for source, target in mapping.items():
        value = row.get(source)
        if value not in (None, ""):
            out[target] = str(value)
    return out


def score(prices: list[float], recent_row: dict[str, Any]) -> tuple[str, dict[str, float]]:
    values = [p for p in prices if p > 0]
    metrics: dict[str, float] = {}
    if values:
        latest = values[-1]
        metrics["latest"] = latest
        if len(values) >= 3:
            med7 = statistics.median(values[-7:])
            med30 = statistics.median(values[-30:])
            metrics["delta7_pct"] = (latest / med7 - 1) * 100 if med7 else 0.0
            metrics["delta30_pct"] = (latest / med30 - 1) * 100 if med30 else 0.0
    current = number(recent_row.get("exmn_dd_cnvs_prc") or recent_row.get("exmn_dd_prc"))
    week = number(recent_row.get("ww1_bfr_cnvs_prc") or recent_row.get("ww1_bfr_prc"))
    month = number(recent_row.get("mm1_bfr_cnvs_prc") or recent_row.get("mm1_bfr_prc"))
    if current is not None and week:
        metrics["recent_week_pct"] = (current / week - 1) * 100
    if current is not None and month:
        metrics["recent_month_pct"] = (current / month - 1) * 100
    strongest = max((metrics.get("delta7_pct", 0), metrics.get("delta30_pct", 0), metrics.get("recent_week_pct", 0), metrics.get("recent_month_pct", 0)))
    if strongest >= 30:
        return "severe", metrics
    if strongest >= 15:
        return "alert", metrics
    if strongest >= 8:
        return "watch", metrics
    return "normal", metrics


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"


def telegram_report(selection: dict[str, Any], level: str, metrics: dict[str, float], counts: dict[str, int], tags: list[str]) -> str:
    item = selection.get("item_nm", "?")
    variety = selection.get("vrty_nm", "")
    grade = selection.get("grd_nm", "")
    side = selection.get("se_nm", "")
    date = selection.get("exmn_ymd", "")
    current = number(selection.get("exmn_dd_cnvs_prc") or selection.get("exmn_dd_prc"))
    lines = [
        f"[{item} {variety} {grade} / {side}] 가격 점검",
        f"- 기준일: {date}",
        f"- 판정: {level} ({', '.join(tags)})",
        f"- 현재가: {current:,.0f}" if current is not None else "- 현재가: n/a",
        f"- 최근 1주 대비: {pct(metrics.get('recent_week_pct'))}",
        f"- 최근 1개월 대비: {pct(metrics.get('recent_month_pct'))}",
        f"- 7일 중앙값 대비: {pct(metrics.get('delta7_pct'))}",
        f"- 30일 중앙값 대비: {pct(metrics.get('delta30_pct'))}",
        f"- 데이터: recent {counts.get('recent', 0)}건 / perDay {counts.get('per_day', 0)}건 / perYearMonth {counts.get('per_year_month', 0)}건 / perRegion {counts.get('per_region', 0)}건",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item", default="배추")
    parser.add_argument("--variety")
    parser.add_argument("--grade", default="상품")
    parser.add_argument("--side", choices=["중도매", "소매"], default="중도매")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--format", choices=["telegram", "json"], default="telegram")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    key = read_key()
    recent_payload = request_json(ENDPOINTS["recent"], common_params(key, 1000))
    recent_rows = extract_items(recent_payload)
    candidates = filter_recent(recent_rows, args.item, args.variety, args.grade, args.side)
    selected = choose_recent(candidates, args.side, args.item)
    if not selected:
        print(f"No recent rows found for item={args.item!r}, variety={args.variety!r}, grade={args.grade!r}, side={args.side!r}", file=sys.stderr)
        return 1

    anchor = parse_ymd(str(selected["exmn_ymd"]))
    start = anchor - dt.timedelta(days=args.days)
    filters = code_filters(selected)

    per_day_params = common_params(key, 1000)
    per_day_params.update(filters)
    per_day_params["cond[exmn_ymd::GTE]"] = ymd(start)
    per_day_params["cond[exmn_ymd::LTE]"] = ymd(anchor)
    per_day_rows = extract_items(request_json(ENDPOINTS["per_day"], per_day_params))
    side_day_rows = [row for row in per_day_rows if row.get("se_cd") == selected.get("se_cd")]
    side_day_rows.sort(key=lambda row: (str(row.get("exmn_ymd", "")), str(row.get("sgg_cd", "")), str(row.get("mrkt_cd", ""))))
    prices = [p for p in (row_price(row) for row in side_day_rows) if p is not None]

    month_params = common_params(key, 1000)
    month_params.update(filters)
    month_params["cond[exmn_ym::GTE]"] = ym(add_months(anchor.replace(day=1), -1))
    month_params["cond[exmn_ym::LTE]"] = ym(anchor)
    month_rows = extract_items(request_json(ENDPOINTS["per_year_month"], month_params))

    region_params = per_day_params.copy()
    region_rows = extract_items(request_json(ENDPOINTS["per_region"], region_params))

    level, metrics = score(prices, selected)
    tags = []
    tags.append("wholesale-only" if args.side == "중도매" else "retail-check")
    if region_rows:
        tags.append("regional")
    else:
        tags.append("region-unavailable")
    if month_rows and metrics.get("recent_month_pct", 0) < 8:
        tags.append("seasonal-normal")

    counts = {
        "recent": len(candidates),
        "per_day": len(per_day_rows),
        "per_year_month": len(month_rows),
        "per_region": len(region_rows),
    }
    result = {
        "selection": selected,
        "level": level,
        "metrics": metrics,
        "counts": counts,
        "tags": tags,
    }
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2 if args.debug else None))
    else:
        print(telegram_report(selected, level, metrics, counts, tags))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
