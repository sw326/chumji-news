#!/usr/bin/env python3
"""Generate report.json for the fresh-food price alert HTML view."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import statistics
import sys
import urllib.parse
import urllib.request
from typing import Any

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from fresh_price_alert import (  # noqa: E402
    ENDPOINTS,
    add_months,
    body,
    code_filters,
    common_params,
    extract_items,
    filter_recent,
    number,
    parse_ymd,
    read_key,
    request_json,
    row_price,
    ym,
    ymd,
)

DEFAULT_OUTPUT_DIR = pathlib.Path.home() / ".openclaw" / "workspace" / "outputs" / "fresh-food-price-alert-view"
DEFAULT_TEMPLATE = DEFAULT_OUTPUT_DIR / "index.html"
GARAK_ENDPOINT = "http://www.garak.co.kr/homepage/publicdata/dataJsonOpen.do"
GARAK_PASSWORD_FILE = pathlib.Path(
    os.getenv(
        "GARAK_PASSWORD_FILE",
        str(pathlib.Path.home() / ".openclaw" / "secrets" / "garak-publicdata-passwd"),
    )
)
GARAK_ITEM_PREFS = {
    "배추": {"name": "배추", "grade": "특", "unit": "10키로망대", "displayUnit": "10키로망대", "divisor": 1},
    "무": {"name": "무", "grade": "특", "unit": "20키로상자", "displayUnit": "개 환산(1.2kg)", "divisor": 20 / 1.2},
    "양파": {"name": "양파", "grade": "특", "unit": "1키로", "displayUnit": "kg 1", "divisor": 1},
    "대파": {"name": "대파(일반)", "grade": "특", "unit": "1키로단", "displayUnit": "kg 1", "divisor": 1},
}
KAMIS_RETAIL_ADJUSTMENTS = {
    "배추": {
        "multiplier": 3,
        "unit": "3포기 환산",
        "note": "KAMIS 소매 포기 가격을 3포기 묶음으로 환산",
    },
    "무": {
        "multiplier": 1,
        "unit": "개 1",
        "note": "가락 무는 20kg 상자를 1개≈1.2kg으로 러프 환산",
    },
}
GARAK_DAY_CACHE: dict[str, list[dict[str, Any]]] = {}


def format_date(value: Any) -> str:
    text = str(value or "")
    if len(text) >= 8:
        return f"{text[4:6]}/{text[6:8]}"
    return "-"


def format_price(value: Any) -> str:
    numeric = number(value)
    if numeric is None:
        return "-"
    return f"{round(numeric):,}"


def format_pct(value: Any) -> str:
    numeric = number(value)
    if numeric is None:
        return "n/a"
    prefix = "+" if numeric > 0 else ""
    return f"{prefix}{numeric:.1f}%"


def points_by_date(points: list[dict[str, Any]]) -> dict[str, Any]:
    return {str(point.get("date")): point.get("price") for point in points if point.get("date")}


def unique_sorted_dates(series_list: list[list[dict[str, Any]]], reverse: bool = False) -> list[str]:
    dates = sorted({str(point.get("date")) for points in series_list for point in points if point.get("date")})
    return list(reversed(dates)) if reverse else dates


def render_note(item: dict[str, Any]) -> str:
    garak = item.get("garak") if isinstance(item.get("garak"), dict) else {}
    kamis = item.get("kamis") if isinstance(item.get("kamis"), dict) else {}
    counts = item.get("counts") if isinstance(item.get("counts"), dict) else {}
    garak_anchor = format_date(garak.get("anchor")) if garak.get("anchor") else "없음"
    kamis_anchor = kamis.get("anchor") or item.get("anchor") or "-"
    adjustment = f" {kamis.get('adjustment')}." if kamis.get("adjustment") else ""
    return (
        f"가락 도매 기준일 {garak_anchor}, KAMIS 소매 기준일 {kamis_anchor}. "
        f"판정 {item.get('level', '-')}. 가락 {counts.get('garak') or 0}일, "
        f"KAMIS 소매 perDay {counts.get('perDay') or 0}건."
        f"{adjustment} 브라우저에는 API 키가 포함되지 않습니다."
    )


def render_rows(item: dict[str, Any]) -> str:
    garak_points_list = item.get("garak", {}).get("points", []) if isinstance(item.get("garak"), dict) else []
    kamis_points_list = item.get("kamis", {}).get("points", []) if isinstance(item.get("kamis"), dict) else item.get("points", [])
    garak_by_date = points_by_date(garak_points_list)
    kamis_by_date = points_by_date(kamis_points_list)
    rows = []
    for date in unique_sorted_dates([garak_points_list, kamis_points_list], reverse=True):
        rows.append(
            "<tr>"
            f"<td>{html.escape(format_date(date))}</td>"
            f"<td>{html.escape(format_price(garak_by_date.get(date)))}</td>"
            f"<td>{html.escape(format_price(kamis_by_date.get(date)))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_static_chart(item: dict[str, Any]) -> str:
    garak_points_list = item.get("garak", {}).get("points", []) if isinstance(item.get("garak"), dict) else []
    kamis_points_list = item.get("kamis", {}).get("points", []) if isinstance(item.get("kamis"), dict) else item.get("points", [])
    dates = unique_sorted_dates([garak_points_list, kamis_points_list])
    prices = [
        number(point.get("price"))
        for point in garak_points_list + kamis_points_list
        if number(point.get("price")) is not None
    ]
    if not dates or not prices:
        return (
            '<svg class="static-chart" viewBox="0 0 760 420" preserveAspectRatio="none" '
            'role="img" aria-label="가격 그래프 데이터 없음"></svg>'
        )

    width, height = 760, 420
    pad = {"top": 26, "right": 28, "bottom": 44, "left": 72}
    plot_w = width - pad["left"] - pad["right"]
    plot_h = height - pad["top"] - pad["bottom"]
    min_price = min(prices)
    max_price = max(prices)
    price_range = max(1, max_price - min_price)
    y_min = min_price - price_range * 0.14
    y_max = max_price + price_range * 0.16
    date_index = {date: index for index, date in enumerate(dates)}

    def x_for(index: int) -> float:
        return pad["left"] + (0 if len(dates) == 1 else (plot_w * index) / (len(dates) - 1))

    def y_for(price: float) -> float:
        return pad["top"] + ((y_max - price) / (y_max - y_min)) * plot_h

    def line(points: list[dict[str, Any]], color: str, width_px: float) -> str:
        coords = []
        circles = []
        label_every = 6
        for point in points:
            date = str(point.get("date"))
            price = number(point.get("price"))
            if date not in date_index or price is None:
                continue
            x = x_for(date_index[date])
            y = y_for(price)
            coords.append(f"{x:.1f},{y:.1f}")
            index = date_index[date]
            if index == 0 or index == len(dates) - 1 or index % label_every == 0:
                circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{color}" />')
        if not coords:
            return ""
        return (
            f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" '
            f'stroke-width="{width_px}" stroke-linecap="round" stroke-linejoin="round" />'
            + "".join(circles)
        )

    grid = []
    for i in range(5):
        price = y_min + ((y_max - y_min) * i) / 4
        y = y_for(price)
        grid.append(f'<line x1="{pad["left"]}" y1="{y:.1f}" x2="{width - pad["right"]}" y2="{y:.1f}" stroke="#d7dde5" />')
        grid.append(
            f'<text x="{pad["left"] - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="12" fill="#667085">{html.escape(format_price(price))}</text>'
        )

    labels = []
    for index, date in enumerate(dates):
        if index != 0 and index != len(dates) - 1 and index % 6 != 0:
            continue
        labels.append(
            f'<text x="{x_for(index):.1f}" y="{height - 18}" text-anchor="middle" '
            f'font-size="12" fill="#667085">{html.escape(format_date(date))}</text>'
        )

    return (
        '<svg class="static-chart" viewBox="0 0 760 420" preserveAspectRatio="none" '
        f'role="img" aria-label="{html.escape(str(item.get("label") or "가격 그래프"))}">'
        '<rect width="760" height="420" fill="#ffffff" />'
        + "".join(grid)
        + line(kamis_points_list, "#1570ef", 2.5)
        + line(garak_points_list, "#d92d20", 3.2)
        + "".join(labels)
        + "</svg>"
    )


def render_buttons(items: list[dict[str, Any]]) -> str:
    buttons = []
    for index, item in enumerate(items):
        text = str(item.get("label") or f"품목 {index + 1}").split(" / ")[0]
        pressed = "true" if index == 0 else "false"
        buttons.append(f'<button type="button" aria-pressed="{pressed}">{html.escape(text)}</button>')
    return "\n".join(buttons)


def render_static_snapshot(template: str, data: dict[str, Any]) -> str:
    items = data.get("items") if isinstance(data.get("items"), list) else []
    if not items:
        return template
    item = items[0]
    generated = str(data.get("generatedAt") or "").replace("T", " ").replace("+09:00", " KST")
    current = item.get("displayCurrent") or item.get("current")
    display_unit = item.get("displayUnit") or item.get("unit") or ""
    garak = item.get("garak") if isinstance(item.get("garak"), dict) else {}
    day_delta = garak.get("deltaDay") if garak.get("deltaDay") is not None else item.get("deltas", {}).get("week")
    month_delta = item.get("deltas", {}).get("month") if isinstance(item.get("deltas"), dict) else None
    replacements = {
        '<div class="meta" id="generated"></div>': f'<div class="meta" id="generated">생성 시각 {html.escape(generated)}</div>',
        '<div class="toolbar" id="itemButtons"></div>': f'<div class="toolbar" id="itemButtons">{render_buttons(items)}</div>',
        '<strong id="metricLabel">-</strong>': f'<strong id="metricLabel">{html.escape(str(item.get("label") or "-"))}</strong>',
        '<strong id="metricCurrent">-</strong>': f'<strong id="metricCurrent">{html.escape(format_price(current) + " (" + str(display_unit) + ")")}</strong>',
        '<strong id="metricWeek">-</strong>': f'<strong id="metricWeek">{html.escape(format_pct(day_delta))}</strong>',
        '<strong id="metricMonth">-</strong>': f'<strong id="metricMonth">{html.escape(format_pct(month_delta))}</strong>',
        '<tbody id="rows"></tbody>': f'<tbody id="rows">{render_rows(item)}</tbody>',
        '<div id="noteText"></div>': f'<div id="noteText">{html.escape(render_note(item))}</div>',
        "<!-- STATIC_CHART -->": render_static_chart(item),
    }
    rendered = template
    for old, new in replacements.items():
        rendered = rendered.replace(old, new, 1)
    return rendered


def choose_recent(rows: list[dict[str, Any]], prefer_side: str, item: str) -> dict[str, Any] | None:
    def sort_key(row: dict[str, Any]) -> tuple[int, int, str, int]:
        exact_item_score = 1 if str(row.get("item_nm", "")) == item else 0
        side_score = 1 if prefer_side in str(row.get("se_nm", "")) else 0
        grade_score = 1 if str(row.get("grd_nm", "")) == "상품" else 0
        return exact_item_score, side_score, str(row.get("exmn_ymd", "")), grade_score

    return max(rows, key=sort_key) if rows else None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    ratio = index - low
    return ordered[low] * (1 - ratio) + ordered[high] * ratio


def read_garak_password() -> str | None:
    password = os.getenv("GARAK_PUBLICDATA_PASSWD", "").strip()
    if password:
        return password
    if GARAK_PASSWORD_FILE.exists():
        return GARAK_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return None


def previous_year(value: dt.date) -> dt.date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value - dt.timedelta(days=365)


def garak_day_rows(password: str, date: dt.date) -> list[dict[str, Any]]:
    key = ymd(date)
    if key in GARAK_DAY_CACHE:
        return GARAK_DAY_CACHE[key]
    previous = date - dt.timedelta(days=1)
    params = {
        "id": "10036",
        "passwd": password,
        "dataid": "data52",
        "pagesize": "1000",
        "pageidx": "1",
        "portal.templet": "false",
        "p_ymd": ymd(date),
        "p_jymd": ymd(previous),
        "d_cd": "2",
        "p_jjymd": ymd(previous_year(date)),
        "p_pos_gubun": "1",
        "pum_nm": "",
    }
    query = urllib.parse.urlencode(params, encoding="euc-kr")
    req = urllib.request.Request(
        f"{GARAK_ENDPOINT}?{query}",
        headers={"User-Agent": "openclaw-fresh-food-price-alert/0.3"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    rows = payload.get("resultData")
    GARAK_DAY_CACHE[key] = rows if isinstance(rows, list) else []
    return GARAK_DAY_CACHE[key]


def garak_price(row: dict[str, Any], divisor: float) -> float | None:
    price = number(row.get("AV_P_A"))
    if not price or price <= 0:
        return None
    return price / divisor if divisor else price


def garak_points(item: str, generated_at: dt.datetime, days: int) -> tuple[list[dict[str, Any]], str | None]:
    password = read_garak_password()
    if not password:
        return [], "missing garak password"
    pref = GARAK_ITEM_PREFS.get(item)
    if not pref:
        return [], f"unsupported garak item: {item}"

    today = generated_at.date()
    start = today - dt.timedelta(days=days)
    points: list[dict[str, Any]] = []
    current = start
    while current <= today:
        try:
            rows = garak_day_rows(password, current)
        except Exception:
            current += dt.timedelta(days=1)
            continue
        matches = [
            row for row in rows
            if str(row.get("PUM_NM_A", "")) == pref["name"]
            and str(row.get("G_NAME_A", "")) == pref["grade"]
            and str(row.get("U_NAME", "")).strip() == pref["unit"]
        ]
        divisor = float(pref.get("divisor") or 1)
        prices = [price for price in (garak_price(row, divisor) for row in matches) if price is not None]
        if prices:
            points.append({"date": ymd(current), "price": round(statistics.median(prices), 1)})
        current += dt.timedelta(days=1)
    return points, None


def build_item(
    key: str,
    item: str,
    side: str,
    grade: str,
    days: int,
    recent_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidates = filter_recent(recent_rows, item, None, grade, side)
    selected = choose_recent(candidates, side, item)
    if not selected:
        raise RuntimeError(f"No recent rows found for {item}/{side}/{grade}")

    anchor = parse_ymd(str(selected["exmn_ymd"]))
    start = anchor - dt.timedelta(days=days)
    filters = code_filters(selected)

    day_params = common_params(key, 1000)
    day_params.update(filters)
    day_params["cond[exmn_ymd::GTE]"] = ymd(start)
    day_params["cond[exmn_ymd::LTE]"] = ymd(anchor)
    day_rows = [
        row for row in extract_items(request_json(ENDPOINTS["per_day"], day_params))
        if row.get("se_cd") == selected.get("se_cd")
    ]

    grouped: dict[str, list[float]] = {}
    for row in day_rows:
        price = row_price(row)
        if price is None:
            continue
        grouped.setdefault(str(row.get("exmn_ymd", "")), []).append(price)
    kamis_adjustment = KAMIS_RETAIL_ADJUSTMENTS.get(item) if side == "소매" else None
    kamis_multiplier = float(kamis_adjustment.get("multiplier", 1)) if kamis_adjustment else 1.0
    points = [
        {"date": date, "price": round(statistics.median(prices), 1)}
        for date, prices in sorted(grouped.items())
        if date
    ]
    if kamis_multiplier != 1:
        points = [
            {"date": point["date"], "price": round(point["price"] * kamis_multiplier, 1)}
            for point in points
        ]

    month_params = common_params(key, 1000)
    month_params.update(filters)
    month_params["cond[exmn_ym::GTE]"] = ym(add_months(anchor.replace(day=1), -1))
    month_params["cond[exmn_ym::LTE]"] = ym(anchor)
    month_rows = extract_items(request_json(ENDPOINTS["per_year_month"], month_params))

    region_rows = extract_items(request_json(ENDPOINTS["per_region"], day_params))
    current = number(selected.get("exmn_dd_cnvs_prc") or selected.get("exmn_dd_prc"))
    week = number(selected.get("ww1_bfr_cnvs_prc") or selected.get("ww1_bfr_prc"))
    month = number(selected.get("mm1_bfr_cnvs_prc") or selected.get("mm1_bfr_prc"))
    if kamis_multiplier != 1:
        current = current * kamis_multiplier if current is not None else None
        week = week * kamis_multiplier if week is not None else None
        month = month * kamis_multiplier if month is not None else None
    prices = [point["price"] for point in points]
    now_kst = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    garak_series, garak_error = garak_points(item, now_kst, days)
    garak_current = garak_series[-1]["price"] if garak_series else None
    garak_previous = garak_series[-2]["price"] if len(garak_series) >= 2 else None
    garak_delta_day = (
        round((garak_current / garak_previous - 1) * 100, 1)
        if garak_current and garak_previous
        else None
    )
    latest = prices[-1] if prices else current
    med7 = statistics.median(prices[-7:]) if prices else None
    med30 = statistics.median(prices[-30:]) if prices else None
    deltas = {
        "week": round((current / week - 1) * 100, 1) if current and week else None,
        "month": round((current / month - 1) * 100, 1) if current and month else None,
        "median7": round((latest / med7 - 1) * 100, 1) if latest and med7 else None,
        "median30": round((latest / med30 - 1) * 100, 1) if latest and med30 else None,
    }
    strongest = max([value for value in deltas.values() if value is not None] or [0])
    level = "normal"
    if strongest >= 30:
        level = "severe"
    elif strongest >= 15:
        level = "alert"
    elif strongest >= 8:
        level = "watch"

    return {
        "label": f"{selected.get('item_nm')} {selected.get('vrty_nm')} {selected.get('grd_nm')} / {selected.get('se_nm')}",
        "anchor": selected.get("exmn_ymd"),
        "unit": f"{selected.get('unit')} {selected.get('unit_sz')}",
        "level": level,
        "current": current,
        "displayCurrent": garak_current or current,
        "displayUnit": GARAK_ITEM_PREFS.get(item, {}).get("displayUnit") or f"{selected.get('unit')} {selected.get('unit_sz')}",
        "deltas": deltas,
        "garak": {
            "anchor": garak_series[-1]["date"] if garak_series else None,
            "current": garak_current,
            "deltaDay": garak_delta_day,
            "unit": GARAK_ITEM_PREFS.get(item, {}).get("displayUnit"),
            "points": garak_series,
            "error": garak_error,
        },
        "kamis": {
            "anchor": selected.get("exmn_ymd"),
            "current": current,
            "unit": kamis_adjustment.get("unit") if kamis_adjustment else f"{selected.get('unit')} {selected.get('unit_sz')}",
            "points": points,
            "adjustment": kamis_adjustment.get("note") if kamis_adjustment else None,
        },
        "counts": {
            "recent": len(candidates),
            "perDay": len(day_rows),
            "perYearMonth": len(month_rows),
            "perRegion": len(region_rows),
            "garak": len(garak_series),
        },
        "range": {
            "low": round(min(prices), 1) if prices else None,
            "high": round(max(prices), 1) if prices else None,
            "p25": round(percentile(prices, 0.25), 1) if prices else None,
            "p75": round(percentile(prices, 0.75), 1) if prices else None,
        },
        "points": points,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--items", nargs="+", default=["배추", "대파", "양파", "무"])
    parser.add_argument("--side", choices=["중도매", "소매"], default="중도매")
    parser.add_argument("--grade", default="상품")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output-dir", type=pathlib.Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--snapshot", action="store_true", help="Also write a self-contained snapshot HTML file with data embedded.")
    parser.add_argument("--template", type=pathlib.Path, default=DEFAULT_TEMPLATE)
    args = parser.parse_args()

    key = read_key()
    generated_at_dt = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).replace(microsecond=0)
    generated_at = generated_at_dt.isoformat()
    data = {
        "generatedAt": generated_at,
        "source": "Garak Market public-data + data.go.kr B552845 KAMIS/aT",
        "items": [],
        "errors": [],
    }
    try:
        recent_payload = request_json(ENDPOINTS["recent"], common_params(key, 1000))
        recent_rows = extract_items(recent_payload)
    except Exception as exc:
        recent_rows = []
        recent_error: Exception | None = exc
    else:
        recent_error = None

    for item in args.items:
        try:
            if recent_error:
                raise recent_error
            data["items"].append(
                build_item(key, item, args.side, args.grade, args.days, recent_rows)
            )
        except Exception as exc:  # keep the view useful even when one item is seasonal/missing
            data["errors"].append({"item": item, "error": str(exc)})

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "report.json"
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.snapshot:
        if not args.template.exists():
            raise SystemExit(f"Snapshot template not found: {args.template}")
        template = args.template.read_text(encoding="utf-8")
        start_marker = "    const fallbackReport = "
        end_marker = "\n\n    let report = fallbackReport;"
        start = template.find(start_marker)
        end = template.find(end_marker, start)
        if end == -1:
            end_marker = "\n\n    var report = fallbackReport;"
            end = template.find(end_marker, start)
        if start == -1 or end == -1:
            raise SystemExit("Could not locate fallbackReport block in template")
        embedded = json.dumps(data, ensure_ascii=False, indent=6)
        stamped = generated_at.replace(":", "").replace("-", "").replace("+", "-").replace("T", "-")
        snapshot = args.output_dir / f"snapshot-{stamped}.html"
        snapshot_html = template[: start + len(start_marker)] + embedded + ";" + template[end:]
        snapshot.write_text(render_static_snapshot(snapshot_html, data), encoding="utf-8")
        print(snapshot)
    print(output)
    return 0 if data["items"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
