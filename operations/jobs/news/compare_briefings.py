#!/usr/bin/env python3
"""Compare cited article URLs in a shadow briefing and a legacy rendering."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from ailess_briefing import canonical_url

MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((https?://[^)\s]+)\)")
HTML_LINK = re.compile(r"href=[\"'](https?://[^\"']+)[\"']", re.IGNORECASE)
IGNORED_HOSTS = {"chumji-news.vercel.app", "www.w3.org"}


def cited_urls(text: str) -> set[str]:
    candidates = MARKDOWN_LINK.findall(text) + HTML_LINK.findall(text)
    urls: set[str] = set()
    for candidate in candidates:
        url = canonical_url(html.unescape(candidate))
        if not url:
            continue
        host = re.sub(r"^www\.", "", url.split("/", 3)[2])
        if host in {re.sub(r"^www\.", "", item) for item in IGNORED_HOSTS}:
            continue
        urls.add(url)
    return urls


def compare(shadow_text: str, legacy_text: str, profile: str) -> dict[str, Any]:
    shadow = cited_urls(shadow_text)
    legacy = cited_urls(legacy_text)
    overlap = shadow & legacy
    union = shadow | legacy
    return {
        "profile": profile,
        "shadow_url_count": len(shadow),
        "legacy_url_count": len(legacy),
        "overlap_count": len(overlap),
        "shadow_overlap_ratio": round(len(overlap) / len(shadow), 4) if shadow else 0,
        "legacy_overlap_ratio": round(len(overlap) / len(legacy), 4) if legacy else 0,
        "jaccard_ratio": round(len(overlap) / len(union), 4) if union else 1,
        "overlap_urls": sorted(overlap),
        "shadow_only_urls": sorted(shadow - legacy),
        "legacy_only_urls": sorted(legacy - shadow),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("morning", "it", "trend"), required=True)
    parser.add_argument("--shadow", type=Path, required=True)
    parser.add_argument("--legacy", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(
        args.shadow.read_text(encoding="utf-8"),
        args.legacy.read_text(encoding="utf-8"),
        args.profile,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
