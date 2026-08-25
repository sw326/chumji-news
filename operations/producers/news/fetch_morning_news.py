#!/usr/bin/env python3
"""
아침 뉴스 브리핑 RSS 수집 스크립트
Usage: python3 fetch_morning_news.py
Output: JSON to stdout
"""

import json
import sys
import urllib.request
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

SOURCES = [
    {
        "name": "BBC",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "category": "해외",
        "limit": 5,
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "해외",
        "limit": 5,
    },
    {
        "name": "조선일보",
        "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
        "category": "보수",
        "limit": 8,
    },
    {
        "name": "경향신문",
        "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml",
        "category": "진보",
        "limit": 8,
    },
    {
        "name": "매일경제",
        "url": "https://www.mk.co.kr/rss/30100041/",
        "category": "증시",
        "limit": 5,
    },
    {
        "name": "연합뉴스",
        "url": "https://www.yna.co.kr/rss/economy.xml",
        "category": "증시",
        "limit": 5,
    },
]

# 제목에 이 키워드가 있으면 제외 (포토, 영상 등)
TITLE_FILTER = ["[포토]", "[영상]", "[광고]", "[현장리뷰]", "[동영상]", "[카드뉴스]"]


def fetch_rss(source):
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
    except Exception as e:
        return [], f"{source['name']}: fetch error — {e}"

    try:
        root = ET.fromstring(raw)
    except Exception as e:
        return [], f"{source['name']}: parse error — {e}"

    articles = []

    # RSS 2.0
    for item in root.findall(".//item"):
        if len(articles) >= source["limit"]:
            break
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        desc = item.findtext("description", "").strip()[:200]

        if not title or not link:
            continue
        if any(kw in title for kw in TITLE_FILTER):
            continue

        articles.append({
            "source": source["name"],
            "category": source["category"],
            "title": title,
            "url": link,
            "summary": desc,
        })

    # Atom feed fallback
    if not articles:
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f".//{{{atom_ns}}}entry"):
            if len(articles) >= source["limit"]:
                break
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link")
            link = (link_el.get("href", "") if link_el is not None else "").strip()
            summary = (entry.findtext(f"{{{atom_ns}}}summary") or "")[:200].strip()
            if not title or not link:
                continue
            articles.append({
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": link,
                "summary": summary,
            })

    if not articles:
        return [], f"{source['name']}: 기사 없음 (피드 구조 확인 필요)"

    return articles, None


def main():
    all_articles = []
    errors = []

    for source in SOURCES:
        articles, err = fetch_rss(source)
        if err:
            errors.append(err)
        all_articles.extend(articles)

    result = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total": len(all_articles),
        "errors": errors,
        "articles": all_articles,
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if errors:
        print(f"\n⚠️ 수집 실패: {len(errors)}개 소스", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
