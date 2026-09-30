#!/usr/bin/env python3
"""Enforce trend collection health without a model or publishing side effects."""
import argparse
import json
from pathlib import Path


def validate_source(payload):
    health = payload.get("collection_health")
    if not isinstance(health, dict) or not health.get("sources"):
        raise ValueError("missing trend collection health")
    sources = health["sources"]
    if any(source.get("status") not in {"ok", "empty", "degraded", "failed"}
           for source in sources):
        raise ValueError("invalid trend source status")
    if health.get("status") == "failed" or all(s["status"] == "failed" for s in sources):
        raise ValueError("all trend sources failed; briefing blocked")
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise ValueError("missing trend articles")
    if sum(s["selected_count"] for s in sources) != len(articles):
        raise ValueError("trend selected counts do not match articles")
    return sources


def collection_notice(payload):
    sources = validate_source(payload)
    missing = [s["name"] for s in sources if s["status"] == "failed"]
    partial = [s["name"] for s in sources if s["status"] == "degraded"]
    parts = []
    if missing:
        parts.append(f"{', '.join(missing)} 미수집")
    if partial:
        parts.append(f"{', '.join(partial)} 일부 수집 실패")
    return f"수집 안내: {'; '.join(parts)}. 수집된 자료만 기준으로 작성.\n" if parts else ""


def empty_briefing(date_kor):
    return f"🔥 {date_kor} IT 트렌드 브리핑\n\n수집된 자료 중 오늘 선정 기준을 충족한 기사가 없습니다.\n"


def add_notice(briefing, payload):
    notice = collection_notice(payload)
    if not notice:
        return briefing
    # Directly under the title, before any model-authored content.
    title, separator, body = briefing.partition("\n")
    if body.startswith("\n" + notice):
        return briefing
    return title + "\n\n" + notice + separator + body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "finalize"])
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--briefing", required=True, type=Path)
    parser.add_argument("--date-kor", default="")
    args = parser.parse_args()
    payload = json.loads(args.source.read_text())
    validate_source(payload)
    if args.action == "prepare":
        if not payload["articles"]:
            args.briefing.write_text(empty_briefing(args.date_kor))
    else:
        args.briefing.write_text(add_notice(args.briefing.read_text(), payload))


if __name__ == "__main__":
    main()
