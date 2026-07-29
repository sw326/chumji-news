#!/usr/bin/env python3
"""Collect recent humanitarian reports from the public ReliefWeb RSS feed."""

from __future__ import annotations

import email.utils
import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

FEED_URL = "https://reliefweb.int/updates/rss.xml"
USER_AGENT = "chumji-ops/1.0 (+https://github.com/sw326/chumji-ops)"

REGIONS = [
    {
        "name": "Ukraine/Russia",
        "code": "UA",
        "terms": ("ukraine", "russia", "russian federation"),
    },
    {
        "name": "Middle East",
        "code": "ME",
        "terms": ("gaza", "israel", "iran", "lebanon", "palestine", "syrian arab republic"),
    },
    {
        "name": "Taiwan Strait",
        "code": "TW",
        "terms": ("taiwan", "taiwan strait"),
    },
    {
        "name": "Korean Peninsula",
        "code": "KP",
        "terms": ("north korea", "dprk", "democratic people's republic of korea"),
    },
    {
        "name": "Sudan/Sahel",
        "code": "SD",
        "terms": ("sudan", "mali", "niger", "burkina faso", "sahel"),
    },
]


def _clean(value: str | None) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = email.utils.parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def fetch_reports(days: int = 7, limit_per_region: int = 5) -> dict:
    request = urllib.request.Request(
        FEED_URL,
        headers={"Accept": "application/rss+xml, application/xml", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            root = ET.fromstring(response.read())
    except Exception as exc:
        return {"error": f"ReliefWeb fetch failed: {exc}", "regions": {}}

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    reports = []
    for item in root.findall("./channel/item"):
        published = _parse_date(item.findtext("pubDate"))
        if published and published < cutoff:
            continue
        title = _clean(item.findtext("title"))
        description_html = item.findtext("description") or ""
        country_match = re.search(
            r'class="tag country"[^>]*>\s*Country:\s*([^<]+)',
            description_html,
            flags=re.IGNORECASE,
        )
        country = _clean(country_match.group(1)) if country_match else ""
        reports.append(
            {
                "title": title,
                "url": _clean(item.findtext("link")),
                "published_at": published.isoformat() if published else None,
                "source": _clean(item.findtext("author")) or "ReliefWeb",
                "category": _clean(item.findtext("category")),
                "country": country,
                "_search": f"{title} {country}".casefold(),
            }
        )

    regions = {}
    for region in REGIONS:
        matches = [
            {key: value for key, value in report.items() if key != "_search"}
            for report in reports
            if any(_contains_term(report["_search"], term) for term in region["terms"])
        ][:limit_per_region]
        regions[region["name"]] = {
            "code": region["code"],
            "report_count": len(matches),
            "reports": matches,
        }

    return {
        "feed_url": FEED_URL,
        "period_days": days,
        "fetched_reports": len(reports),
        "regions": regions,
    }
