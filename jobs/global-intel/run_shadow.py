#!/usr/bin/env python3
"""Generate a deterministic, publication-free global-intel shadow report."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re

import fetch_acled
import fetch_gdelt
import fetch_opensky
import fetch_reliefweb

POLICY_VERSION = "ailess-global-intel-v2"


def error_category(value) -> str | None:
    if not value:
        return None
    text = str(value).casefold()
    if "account_temporarily_blocked" in text or "flood_user_blocked" in text:
        return "account_temporarily_blocked"
    if "invalid_grant" in text or "authentication failed" in text:
        return "invalid_credentials"
    if "403" in text or "forbidden" in text:
        return "http_403"
    if "429" in text or "too many" in text:
        return "http_429"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "ssl" in text or "handshake" in text:
        return "tls"
    if "missing" in text or "미설정" in text:
        return "missing_credentials"
    return "request_error"


def collect() -> dict:
    acled = fetch_acled.fetch_recent_events(days=7)
    reliefweb = fetch_reliefweb.fetch_reports(days=7)
    gdelt_regions = {}
    if os.environ.get("GDELT_ENABLED") == "1":
        for region in fetch_gdelt.REGIONS:
            gdelt_regions[region["name"]] = {
                "code": region["code"],
                **fetch_gdelt.fetch_region_events(region["query"], days=1),
            }
    opensky_zones = {}
    for zone in fetch_opensky.ZONES:
        opensky_zones[zone["name"]] = fetch_opensky.fetch_zone(zone)
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "acled": acled,
        "reliefweb": reliefweb,
        "gdelt": {
            "enabled": os.environ.get("GDELT_ENABLED") == "1",
            "regions": gdelt_regions,
        },
        "opensky": {"zones": opensky_zones},
    }


def source_health(payload: dict) -> dict:
    acled_error = error_category(payload["acled"].get("error"))
    reliefweb_error = error_category(payload["reliefweb"].get("error"))
    gdelt_errors = {
        name: error_category(data.get("error"))
        for name, data in payload["gdelt"]["regions"].items()
        if data.get("error")
    }
    opensky_errors = {
        name: error_category(data.get("error"))
        for name, data in payload["opensky"]["zones"].items()
        if data.get("error")
    }
    return {
        "acled": {
            "status": "error" if acled_error else "ok",
            "error": acled_error,
        },
        "reliefweb": {
            "status": "error" if reliefweb_error else "ok",
            "error": reliefweb_error,
            "successful_regions": sum(
                1
                for region in payload["reliefweb"].get("regions", {}).values()
                if region.get("report_count", 0) > 0
            ),
            "total_regions": len(payload["reliefweb"].get("regions", {})),
        },
        "gdelt": {
            "status": "disabled" if not payload["gdelt"].get("enabled") else (
                "ok" if not gdelt_errors else (
                "error" if len(gdelt_errors) == len(payload["gdelt"]["regions"])
                else "partial"
                )
            ),
            "successful_regions": len(payload["gdelt"]["regions"]) - len(gdelt_errors),
            "total_regions": len(payload["gdelt"]["regions"]),
            "errors": gdelt_errors,
        },
        "opensky": {
            "status": "ok" if not opensky_errors else "partial",
            "successful_zones": len(payload["opensky"]["zones"]) - len(opensky_errors),
            "total_zones": len(payload["opensky"]["zones"]),
            "errors": opensky_errors,
        },
    }


def render_markdown(payload: dict, health: dict, run_date: str) -> str:
    lines = [
        f"# {run_date} 국제정세 데이터 점검",
        "",
        "> AI 없이 공개 데이터의 상태와 관측값만 정리했습니다. 항공기 수나 무콜사인 항공기는 군사 활동의 증거가 아닙니다.",
        "",
        "## 소스 상태",
        "",
        f"- ACLED: {health['acled']['status']}"
        + (f" ({health['acled']['error']})" if health["acled"]["error"] else ""),
        f"- ReliefWeb: {health['reliefweb']['status']} "
        f"({health['reliefweb']['successful_regions']}/{health['reliefweb']['total_regions']} 권역)",
        f"- GDELT: {health['gdelt']['status']} "
        f"({health['gdelt']['successful_regions']}/{health['gdelt']['total_regions']} 지역)",
        f"- OpenSky: {health['opensky']['status']} "
        f"({health['opensky']['successful_zones']}/{health['opensky']['total_zones']} 권역)",
        "",
    ]

    acled_summary = payload["acled"].get("summary")
    lines.extend(["## ACLED 분쟁 이벤트", ""])
    if isinstance(acled_summary, dict):
        lines.extend([
            f"- 최근 사건: {acled_summary.get('total_events', 0)}건",
            f"- 사망자 합계: {acled_summary.get('total_fatalities', 0)}명",
            f"- 영향 국가: {acled_summary.get('countries_affected', 0)}개",
        ])
    else:
        lines.append("- 데이터 없음: 인증 또는 API 상태를 확인해야 합니다.")
    lines.append("")

    lines.extend(["## ReliefWeb 상황 보고", ""])
    citations = []
    reliefweb_error = error_category(payload["reliefweb"].get("error"))
    if reliefweb_error:
        lines.append(f"- 수집 실패 ({reliefweb_error})")
    for name, region in payload["reliefweb"].get("regions", {}).items():
        lines.append(f"- {name}: 최근 보고서 {region.get('report_count', 0)}건")
        for report in region.get("reports", [])[:2]:
            url = str(report.get("url") or "")
            title = re.sub(r"\s+", " ", str(report.get("title") or "")).strip()
            if title and url.startswith(("http://", "https://")):
                citations.append((title, url, report.get("source") or "ReliefWeb"))
    lines.append("")

    lines.extend(["## GDELT 뉴스 긴장도", ""])
    if not payload["gdelt"].get("enabled"):
        lines.append("- 반복적인 HTTP 429로 기본 비활성화했습니다.")
    for name, region in payload["gdelt"]["regions"].items():
        category = error_category(region.get("error"))
        if category:
            lines.append(f"- {name}: 수집 실패 ({category})")
            continue
        lines.append(
            f"- {name}: {region.get('tension_level', 'UNKNOWN')} "
            f"(기사 {region.get('article_count', 0)}건, 평균 tone {region.get('avg_tone', 0)})"
        )
        for article in region.get("top_articles", [])[:2]:
            url = str(article.get("url") or "")
            title = re.sub(r"\s+", " ", str(article.get("title") or "")).strip()
            if title and url.startswith(("http://", "https://")):
                citations.append((title, url, article.get("source") or "GDELT"))
    lines.append("")

    lines.extend(["## OpenSky 항공 관측", ""])
    for name, zone in payload["opensky"]["zones"].items():
        category = error_category(zone.get("error"))
        if category:
            lines.append(f"- {name}: 수집 실패 ({category})")
            continue
        lines.append(
            f"- {name}: 비행 중 {zone.get('total_aircraft', 0)}대, "
            f"무콜사인 {zone.get('no_callsign_count', 0)}대"
        )
    lines.extend([
        "",
        "_주의: OpenSky는 민항 중심의 불완전한 수신 데이터이며, 단일 시점 수치만으로 긴장 상승을 판정하지 않습니다._",
    ])

    if citations:
        lines.extend(["", "## 근거 기사", ""])
        for title, url, source in citations[:10]:
            lines.append(f"- [{title}]({url}) · {source}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=pathlib.Path, required=True)
    parser.add_argument("--acled-secret-file", type=pathlib.Path)
    args = parser.parse_args()
    if args.acled_secret_file:
        os.environ["ACLED_SECRET_FILE"] = str(args.acled_secret_file)
        # The imported module loads at import time; load approved values here
        # without printing them.
        if args.acled_secret_file.exists():
            for line in args.acled_secret_file.read_text().splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
            fetch_acled.ACLED_EMAIL = os.environ.get("ACLED_EMAIL", "")
            fetch_acled.ACLED_PASSWORD = os.environ.get("ACLED_PASSWORD", "")

    run_date = dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    output_dir = args.output_root / run_date
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = collect()
    health = source_health(payload)
    raw_path = output_dir / "sources.json"
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = render_markdown(payload, health, run_date)
    briefing_path = output_dir / "briefing.md"
    briefing_path.write_text(markdown, encoding="utf-8")
    status = {
        "run_date": run_date,
        "generated_at": payload["generated_at"],
        "policy_version": POLICY_VERSION,
        "model_route": "none",
        "publication": "disabled",
        "source_health": health,
        "briefing_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
    }
    (output_dir / "shadow-status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(status, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
