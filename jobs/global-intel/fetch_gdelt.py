#!/usr/bin/env python3
"""
GDELT 지역별 긴장도·뉴스 이벤트 수집
https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/

인증 불필요. 15분 단위 업데이트.
Output: JSON { tension_by_region: {...}, top_events: [...] }
"""

import json
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone


# GDELT GKG (Global Knowledge Graph) 긴장도 쿼리
# 지역별 Goldstein Scale 평균 (음수 = 분쟁/긴장, 양수 = 협력)
GDELT_EVENTS_URL = "https://api.gdeltproject.org/api/v2/events/query"

# 관심 지역 + 검색 쿼리
REGIONS = [
    {"name": "Ukraine/Russia", "query": "Ukraine OR Russia", "code": "UA"},
    {"name": "Middle East", "query": "Gaza OR Lebanon OR Israel OR Iran", "code": "ME"},
    {"name": "Taiwan Strait", "query": "Taiwan OR PLA", "code": "TW"},
    {"name": "Korean Peninsula", "query": "North Korea OR DPRK", "code": "KP"},
    {"name": "Sudan/Sahel", "query": "Sudan OR Mali OR Niger", "code": "SD"},
]

def fetch_region_events(query: str, days: int = 1) -> dict:
    """특정 지역/키워드의 최근 이벤트 수집"""
    # GDELT DOC API (뉴스 기사 기반)
    doc_url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": "10",
        "format": "json",
        "timespan": f"{days}d",
        "sort": "ToneDesc",  # 부정적 tone 우선
    }
    url = doc_url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "global-intel/1.0"})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        articles = data.get("articles", [])
        # 평균 tone 계산 (음수 = 부정적/긴장)
        tones = [float(a.get("tone", "0")) for a in articles if a.get("tone")]
        avg_tone = sum(tones) / len(tones) if tones else 0
        return {
            "article_count": len(articles),
            "avg_tone": round(avg_tone, 2),
            "tension_level": "HIGH" if avg_tone < -5 else "MEDIUM" if avg_tone < -2 else "LOW",
            "top_articles": [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "source": a.get("domain", ""),
                    "tone": a.get("tone", ""),
                    "seendate": a.get("seendate", ""),
                }
                for a in articles[:5]
            ],
        }
    except Exception as e:
        return {"error": str(e), "article_count": 0, "avg_tone": 0, "tension_level": "UNKNOWN"}


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "regions": {},
    }

    for region in REGIONS:
        data = fetch_region_events(region["query"], days=days)
        result["regions"][region["name"]] = {
            "code": region["code"],
            **data,
        }

    # 긴장도 순 정렬
    sorted_regions = sorted(
        result["regions"].items(),
        key=lambda x: x[1].get("avg_tone", 0)
    )
    result["hotspots"] = [
        {"region": k, "tone": v.get("avg_tone", 0), "level": v.get("tension_level", "?")}
        for k, v in sorted_regions[:3]
    ]

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
