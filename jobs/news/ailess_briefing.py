#!/usr/bin/env python3
"""Deterministic, model-free news briefing generator."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

POLICY_VERSION = "ailess-news-v3"
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source"}
TRACKING_PREFIXES = ("utm_",)
IT_TOPIC_TOKENS = {
    "ai", "앱", "보안", "기술", "로봇", "모델", "반도체", "배터리", "소프트웨어",
    "스마트폰", "오픈소스", "인공지능", "자동차", "전기차", "컴퓨팅", "클라우드",
    "플랫폼", "해킹", "데이터", "security", "software", "tech", "robot", "chip",
    "agent", "api", "app", "cloud", "code", "commit", "computer", "cyber",
    "developer", "device", "digital", "github", "gpu", "internet", "iphone",
    "llm", "linux", "microsoft", "openai", "python", "startup", "tesla", "web",
    "개발", "네트워크", "디지털", "버그", "서버", "스타트업", "애플",
    "에이전트", "인터넷", "코드", "컴퓨터", "테슬라", "프로그래밍",
}
IT_OFFTOPIC_TOKENS = {
    "대통령", "트럼프", "네타냐후", "젤렌스키", "전쟁", "종전", "미사일",
    "회담", "선거", "국회", "관세", "코스피", "코스닥", "한터차트", "아이돌",
    "커피", "영화", "채용", "구인", "is hiring", "war", "election", "president",
}

PROFILES = {
    "morning": {
        "label": "아침 뉴스",
        "limit": 18,
        "per_source": 4,
        "signals": {
            "속보": 3,
            "발표": 2,
            "확정": 2,
            "합의": 2,
            "인상": 1,
            "인하": 1,
            "전망": 1,
        },
    },
    "it": {
        "label": "IT·테크",
        "limit": 10,
        "per_source": 3,
        "max_english": 4,
        "signals": {
            "release": 2,
            "launch": 2,
            "open source": 2,
            "security": 2,
            "ai": 1,
            "출시": 2,
            "공개": 2,
            "보안": 2,
            "오픈소스": 2,
        },
    },
    "trend": {
        "label": "트렌드",
        "limit": 18,
        "per_source": 4,
        "signals": {
            "how": 1,
            "why": 1,
            "show hn": 2,
            "무료": 2,
            "할인": 2,
            "출시": 1,
            "화제": 2,
            "논란": 1,
        },
    },
}


@dataclass(frozen=True)
class Article:
    source: str
    category: str
    title: str
    url: str
    summary: str
    input_index: int
    score: int


def clean_text(value: Any, limit: int) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def clean_summary(value: Any, limit: int = 180) -> str:
    text = clean_text(value, 2_000)
    text = re.sub(
        r"\bArticle URL:.*?(?=(?:Comments URL:|Points:|$))", " ", text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:Comments URL|Points|# Comments):.*", " ", text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"^submitted by\s+/?u?/?[^\s]+(?:\s+\[[^\]]*)?\s*", "", text,
                  flags=re.IGNORECASE)
    if re.match(r"^submitted by\b", text, flags=re.IGNORECASE):
        return ""
    text = re.sub(r"\b(?:Discussion|Link)\s*(?:\||$)", " ", text,
                  flags=re.IGNORECASE)
    text = re.sub(r"\s*(?:<[^>]*|\[[^\]]*)$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" []|")
    if not text:
        return ""

    sentences = re.split(r"(?<=[.!?。！？])\s+", text)
    summary = " ".join(sentences[:2]).strip()
    if len(summary) <= limit:
        return summary
    shortened = summary[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return (shortened or summary[:limit]).rstrip() + "…"


def canonical_url(value: Any) -> str:
    raw = clean_text(value, 2_000)
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return ""
    query = [
        (key, val)
        for key, val in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS
        and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), "")
    )


def normalized_title(title: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]+", "", title.casefold())


def title_score(title: str, signals: dict[str, int]) -> int:
    lowered = title.casefold()
    return sum(weight for token, weight in signals.items() if token in lowered)


def is_it_offtopic(title: str) -> bool:
    lowered = title.casefold()
    return (
        any(token in lowered for token in IT_OFFTOPIC_TOKENS)
        and not any(token in lowered for token in IT_TOPIC_TOKENS)
    )


def is_it_relevant(title: str) -> bool:
    return any(token in title.casefold() for token in IT_TOPIC_TOKENS)


def title_terms(title: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[0-9a-z가-힣]+", title.casefold())
        if len(token) >= 2
    }


def is_similar_title(title: str, previous: list[str], threshold: float = 0.62) -> bool:
    terms = title_terms(title)
    if not terms:
        return False
    for item in previous:
        other = title_terms(item)
        union = terms | other
        if union and len(terms & other) / len(union) >= threshold:
            return True
    return False


def is_english_title(title: str) -> bool:
    latin = len(re.findall(r"[A-Za-z]", title))
    hangul = len(re.findall(r"[가-힣]", title))
    return latin >= 8 and latin > hangul * 2


def select_articles(
    payload: dict[str, Any], profile_name: str
) -> tuple[list[Article], dict[str, Any]]:
    profile = PROFILES[profile_name]
    raw_articles = payload.get("articles")
    if not isinstance(raw_articles, list):
        raise ValueError("input JSON must contain an articles array")

    rejected = Counter()
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    candidates: list[Article] = []

    for index, raw in enumerate(raw_articles):
        if not isinstance(raw, dict):
            rejected["invalid_record"] += 1
            continue
        title = clean_text(raw.get("title"), 240)
        source = clean_text(raw.get("source"), 80)
        url = canonical_url(raw.get("url"))
        if not title or not source or not url:
            rejected["missing_required_field"] += 1
            continue
        summary = clean_summary(raw.get("summary"))
        if profile_name == "it":
            if is_it_offtopic(title) or not is_it_relevant(title):
                rejected["category_offtopic"] += 1
                continue
            if not summary:
                rejected["missing_summary"] += 1
                continue
        title_key = normalized_title(title)
        if url in seen_urls or title_key in seen_titles:
            rejected["duplicate"] += 1
            continue
        seen_urls.add(url)
        seen_titles.add(title_key)
        candidates.append(
            Article(
                source=source,
                category=clean_text(raw.get("category"), 60) or "기타",
                title=title,
                url=url,
                summary=summary,
                input_index=index,
                score=title_score(title, profile["signals"]),
            )
        )

    candidates.sort(key=lambda article: (-article.score, article.input_index))
    source_counts: Counter[str] = Counter()
    selected: list[Article] = []
    selected_keys: set[tuple[str, str]] = set()
    selected_titles: list[str] = []
    english_count = 0

    def can_select(article: Article) -> bool:
        if is_similar_title(article.title, selected_titles):
            rejected["semantic_duplicate"] += 1
            return False
        maximum = profile.get("max_english")
        if maximum is not None and is_english_title(article.title) and english_count >= maximum:
            rejected["english_quota"] += 1
            return False
        return True

    def add_selected(article: Article) -> None:
        nonlocal english_count
        selected.append(article)
        selected_keys.add((article.source, article.url))
        selected_titles.append(article.title)
        source_counts[article.source] += 1
        if is_english_title(article.title):
            english_count += 1

    # Seed one high-scoring item per source before filling the remaining slots.
    # This makes source coverage explicit instead of relying on feed order.
    for article in candidates:
        if source_counts[article.source]:
            continue
        if not can_select(article):
            continue
        add_selected(article)
        if len(selected) >= profile["limit"]:
            break

    for article in candidates:
        if (article.source, article.url) in selected_keys:
            continue
        if source_counts[article.source] >= profile["per_source"]:
            rejected["source_quota"] += 1
            continue
        if not can_select(article):
            continue
        add_selected(article)
        if len(selected) >= profile["limit"]:
            break

    selected.sort(key=lambda article: (-article.score, article.input_index))

    input_sources = {
        clean_text(item.get("source"), 80)
        for item in raw_articles
        if isinstance(item, dict) and clean_text(item.get("source"), 80)
    }
    report = {
        "policy_version": POLICY_VERSION,
        "profile": profile_name,
        "model_route": "none",
        "input_count": len(raw_articles),
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "input_source_count": len(input_sources),
        "selected_source_count": len(source_counts),
        "selected_by_source": dict(sorted(source_counts.items())),
        "selected_english_count": english_count,
        "rejected": dict(sorted(rejected.items())),
    }
    return selected, report


def render_markdown(articles: list[Article], profile_name: str, run_date: str) -> str:
    label = PROFILES[profile_name]["label"]
    grouped: dict[str, list[Article]] = defaultdict(list)
    for article in articles:
        grouped[article.category].append(article)

    lines = [
        f"# {run_date} {label}",
        "",
        f"> AI 없이 공개 피드에서 규칙 기반으로 선별한 {len(articles)}건입니다.",
        "",
    ]
    for category, items in grouped.items():
        lines.extend([f"## {category}", ""])
        for article in items:
            language = " · 영문" if is_english_title(article.title) else ""
            lines.append(
                f"- [{article.title}]({article.url}) · {article.source}{language}"
            )
            if article.summary:
                lines.append(f"  - {article.summary}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run(profile: str, input_path: Path, output_dir: Path, run_date: str) -> dict[str, Any]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    articles, report = select_articles(payload, profile)
    markdown = render_markdown(articles, profile, run_date)
    output_dir.mkdir(parents=True, exist_ok=True)
    briefing_path = output_dir / f"{profile}-briefing.md"
    report_path = output_dir / f"{profile}-report.json"
    briefing_path.write_text(markdown, encoding="utf-8")
    report.update(
        {
            "run_date": run_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "briefing_sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "publication": "disabled",
        }
    )
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--date", default=datetime.now().astimezone().strftime("%Y-%m-%d")
    )
    args = parser.parse_args()
    report = run(args.profile, args.input, args.output_dir, args.date)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
