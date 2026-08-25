#!/usr/bin/env python3
"""
IT/테크 뉴스 RSS 수집 스크립트
Usage: python3 fetch_it_tech.py
Output: JSON array of articles to stdout
"""

import json
import sys
import urllib.request
from xml.etree import ElementTree as ET
from datetime import datetime, timezone

SOURCES = [
    {
        "name": "TechCrunch",
        "url": "https://techcrunch.com/feed/",
        "category": "해외",
        "limit": 5,
    },
    {
        "name": "The Verge",
        "url": "https://www.theverge.com/rss/index.xml",
        "category": "해외",
        "limit": 5,
    },
    {
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "category": "해외",
        "limit": 5,
    },
    {
        "name": "GeekNews",
        "url": "https://news.hada.io/rss/news",
        "category": "국내",
        "limit": 5,
    },
    {
        "name": "AI타임즈",
        "url": "https://www.aitimes.com/rss/allArticle.xml",
        "category": "국내",
        "limit": 5,
    },
    {
        "name": "전자신문",
        "url": "https://rss.etnews.com/Section901.xml",
        "category": "국내",
        "limit": 5,
    },
]

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def fetch_rss(source):
    url = source["url"]
    try:
        req = urllib.request.Request(
            url,
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
    for item in root.findall(".//item")[: source["limit"]]:
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        desc = item.findtext("description", "").strip()[:200]
        if not title or not link:
            continue
        # 홈페이지 루트 URL 필터링
        if link.rstrip("/") in (url.rstrip("/"), source["url"].rstrip("/")):
            continue
        articles.append(
            {
                "source": source["name"],
                "category": source["category"],
                "title": title,
                "url": link,
                "summary": desc,
            }
        )

    # Atom feed
    if not articles:
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f".//{{{atom_ns}}}entry")[: source["limit"]]:
            title = (entry.findtext(f"{{{atom_ns}}}title") or "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link")
            link = (link_el.get("href", "") if link_el is not None else "").strip()
            summary = (entry.findtext(f"{{{atom_ns}}}summary") or "")[:200].strip()
            if not title or not link:
                continue
            articles.append(
                {
                    "source": source["name"],
                    "category": source["category"],
                    "title": title,
                    "url": link,
                    "summary": summary,
                }
            )

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
