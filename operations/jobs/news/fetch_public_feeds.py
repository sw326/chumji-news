#!/usr/bin/env python3
"""Fetch public RSS/Atom feeds for the AI-less news shadow job."""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

USER_AGENT = "chumji-news-shadow/1.0 (+https://github.com/sw326/chumji-news)"

SOURCES: dict[str, list[dict[str, Any]]] = {
    "morning": [
        {"name": "BBC", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "category": "해외", "limit": 8},
        {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "해외", "limit": 8},
        {"name": "조선일보", "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml", "category": "국내", "limit": 6},
        {"name": "경향신문", "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml", "category": "국내", "limit": 6},
        {"name": "매일경제", "url": "https://www.mk.co.kr/rss/30100041/", "category": "경제", "limit": 4},
        {"name": "연합뉴스 경제", "url": "https://www.yna.co.kr/rss/economy.xml", "category": "경제", "limit": 4},
    ],
    "it": [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "category": "해외", "limit": 6},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml", "category": "해외", "limit": 6},
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "해외", "limit": 6},
        {"name": "GeekNews", "url": "https://news.hada.io/rss/news", "category": "국내", "limit": 4},
        {"name": "AI타임즈", "url": "https://www.aitimes.com/rss/allArticle.xml", "category": "국내", "limit": 4},
        {"name": "전자신문", "url": "https://rss.etnews.com/Section901.xml", "category": "국내", "limit": 4},
    ],
    "trend": [
        {"name": "Hacker News", "url": "https://hnrss.org/frontpage", "category": "해외버즈", "limit": 6},
        {"name": "Reddit r/technology", "url": "https://www.reddit.com/r/technology/.rss", "category": "해외버즈", "limit": 6},
        {"name": "Product Hunt", "url": "https://www.producthunt.com/feed", "category": "해외버즈", "limit": 6},
        {"name": "GeekNews", "url": "https://news.hada.io/rss/news", "category": "국내커뮤니티", "limit": 6},
        {"name": "ZDNet Korea", "url": "https://zdnet.co.kr/feed/", "category": "국내커뮤니티", "limit": 6},
        {"name": "뽐뿌 컴퓨터", "url": "https://www.ppomppu.co.kr/rss.php?id=computer", "category": "핫딜", "limit": 4},
    ],
}


def node_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", "".join(node.itertext())).strip()


def parse_feed(data: bytes, source: dict[str, Any]) -> list[dict[str, str]]:
    root = ET.fromstring(data)
    records: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = node_text(item.find("title"))
        url = node_text(item.find("link"))
        summary = node_text(item.find("description"))
        if title and url:
            records.append(
                {
                    "source": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": url,
                    "summary": summary[:800],
                }
            )
        if len(records) >= source["limit"]:
            return records

    atom = "{http://www.w3.org/2005/Atom}"
    for entry in root.findall(f".//{atom}entry"):
        title = node_text(entry.find(f"{atom}title"))
        link = entry.find(f"{atom}link")
        url = (link.get("href") or "").strip() if link is not None else ""
        summary = node_text(entry.find(f"{atom}summary")) or node_text(
            entry.find(f"{atom}content")
        )
        if title and url:
            records.append(
                {
                    "source": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": url,
                    "summary": summary[:800],
                }
            )
        if len(records) >= source["limit"]:
            break
    return records


def fetch_profile(profile: str, timeout: float = 12.0) -> dict[str, Any]:
    articles: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    coverage: dict[str, int] = {}
    for source in SOURCES[profile]:
        try:
            request = urllib.request.Request(
                source["url"], headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                records = parse_feed(response.read(), source)
            coverage[source["name"]] = len(records)
            articles.extend(records)
            if not records:
                errors.append({"source": source["name"], "error": "no_items"})
        except Exception as exc:
            coverage[source["name"]] = 0
            errors.append(
                {"source": source["name"], "error": type(exc).__name__}
            )
    return {
        "profile": profile,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total": len(articles),
        "coverage": coverage,
        "errors": errors,
        "articles": articles,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(SOURCES), required=True)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args()
    print(
        json.dumps(
            fetch_profile(args.profile, args.timeout),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
