#!/usr/bin/env python3
"""Compare Korean customs trade statistics by HS code and country."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from trade_data_model import KoreanCustomsAdapter, TradeObservation


CUSTOMS_URL = "https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList"
DEFAULT_KEY_FILE = Path.home() / ".config" / "data-go-kr" / "api_key"


def load_api_key(key_file: Path) -> str:
    key = os.environ.get("DATA_GO_KR_API_KEY", "").strip()
    if key:
        return key
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"API 키가 없습니다. DATA_GO_KR_API_KEY 또는 {key_file}을 설정하세요."
        ) from exc
    if not key:
        raise RuntimeError(f"API 키 파일이 비어 있습니다: {key_file}")
    return key


def request_xml(params: dict[str, str], timeout: float) -> bytes:
    request = urllib.request.Request(
        f"{CUSTOMS_URL}?{urllib.parse.urlencode(params)}",
        headers={"User-Agent": "trade-market-briefing/0.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"관세청 API 호출 실패: {exc}") from exc


def parse_customs_xml(payload: bytes) -> list[dict[str, Any]]:
    if not payload:
        raise RuntimeError("관세청 API가 빈 응답을 반환했습니다.")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        preview = payload[:160].decode("utf-8", errors="replace")
        raise RuntimeError(f"XML이 아닌 응답입니다: {preview}") from exc

    code = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode") or ""
    message = root.findtext(".//resultMsg") or root.findtext(".//returnAuthMsg") or ""
    if code not in {"00", "0"}:
        raise RuntimeError(f"관세청 API 오류: {message or '알 수 없음'} (코드 {code})")

    integer_fields = {"expWgt", "expDlr", "impWgt", "impDlr", "balPayments"}
    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        item: dict[str, Any] = {}
        for child in node:
            value: Any = child.text or ""
            if child.tag in integer_fields:
                try:
                    value = int(value.replace(",", ""))
                except ValueError:
                    value = 0
            item[child.tag] = value
        items.append(item)
    return items


def fetch_country(
    api_key: str,
    country_code: str,
    start_yymm: str,
    end_yymm: str,
    hs_code: str | None,
    timeout: float,
) -> list[dict[str, Any]]:
    params = {
        "serviceKey": api_key,
        "strtYymm": start_yymm,
        "endYymm": end_yymm,
        "cntyCd": country_code.upper(),
    }
    if hs_code:
        params["hsSgn"] = hs_code
    return parse_customs_xml(request_xml(params, timeout))


def normalize_customs_items(
    items: list[dict[str, Any]], classification_version: str = "HSK"
) -> list[TradeObservation]:
    return KoreanCustomsAdapter(classification_version).normalize(items)


def aggregate(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(
        lambda: {"export_usd": 0, "import_usd": 0, "export_kg": 0, "import_kg": 0}
    )
    for item in items:
        if str(item.get("hsCd", "")) in {"", "-"} or str(item.get("statCd", "")) in {"", "-"}:
            # 관세청 응답에는 전체 합계 행이 함께 섞일 수 있다.
            continue
        key = (
            str(item.get("statCd", "")),
            str(item.get("hsCd", "")),
            str(item.get("statKor", "")),
        )
        row = grouped[key]
        row["country_code"] = key[0]
        row["country_name"] = item.get("statCdCntnKor1", "")
        row["hs_code"] = key[1]
        row["item_name"] = key[2]
        row["export_usd"] += int(item.get("expDlr", 0) or 0)
        row["import_usd"] += int(item.get("impDlr", 0) or 0)
        row["export_kg"] += int(item.get("expWgt", 0) or 0)
        row["import_kg"] += int(item.get("impWgt", 0) or 0)
        row["balance_usd"] = row["export_usd"] - row["import_usd"]
    return list(grouped.values())


def format_usd(value: int) -> str:
    if abs(value) >= 100_000_000:
        return f"{value / 100_000_000:,.1f}억 달러"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:,.1f}백만 달러"
    return f"{value:,}달러"


def render_comparison(
    rows: list[dict[str, Any]], start_yymm: str, end_yymm: str, hs_code: str | None
) -> str:
    title = f"HS {hs_code} 국가별 수출입 비교" if hs_code else "국가별 전체 품목 수출입"
    lines = [f"# {title}", "", f"조회기간: {start_yymm}~{end_yymm}", ""]
    if not rows:
        return "\n".join(lines + ["조회된 데이터가 없습니다.", ""])
    rows = sorted(rows, key=lambda row: int(row["export_usd"]), reverse=True)
    lines += [
        "| 국가 | HS코드 | 품목 | 수출액 | 수입액 | 무역수지 |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        country = row.get("country_name") or row.get("country_code")
        lines.append(
            f"| {country} | {row.get('hs_code', '')} | {row.get('item_name', '')} | "
            f"{format_usd(int(row['export_usd']))} | {format_usd(int(row['import_usd']))} | "
            f"{format_usd(int(row['balance_usd']))} |"
        )
    lines += [
        "",
        "출처: 관세청 품목별 국가별 수출입실적(GW). 수출은 FOB, 수입은 CIF 기준입니다.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="HS코드·국가별 수출입 비교")
    parser.add_argument("--countries", required=True, help="쉼표로 구분한 ISO2 코드 (US,CN,JP)")
    parser.add_argument("--start", required=True, help="시작년월 YYYYMM")
    parser.add_argument("--end", required=True, help="종료년월 YYYYMM, 시작부터 최대 1년")
    parser.add_argument("--hs-code", help="HS 2/4/6/10자리. 생략하면 국가별 전체 품목")
    parser.add_argument("--top", type=int, default=50, help="수출액 기준 표시 행 수")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--key-file", type=Path, default=DEFAULT_KEY_FILE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    try:
        api_key = load_api_key(args.key_file)
        all_items: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for country in [value.strip().upper() for value in args.countries.split(",") if value.strip()]:
            try:
                all_items.extend(
                    fetch_country(api_key, country, args.start, args.end, args.hs_code, args.timeout)
                )
            except RuntimeError as exc:
                errors[country] = str(exc)
        rows = sorted(aggregate(all_items), key=lambda row: int(row["export_usd"]), reverse=True)
        markdown = render_comparison(rows[: args.top], args.start, args.end, args.hs_code)
        if errors:
            markdown += "\n## 조회 제한\n\n" + "\n".join(
                f"- {country}: {message}" for country, message in errors.items()
            ) + "\n"
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(
                {
                    "rows": rows,
                    "observations": [
                        observation.to_dict() for observation in normalize_customs_items(all_items)
                    ],
                    "errors": errors,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
