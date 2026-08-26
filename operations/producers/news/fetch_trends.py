#!/usr/bin/env python3
"""Discover trend candidates from public feeds and select them deterministically.

RSS is a discovery surface, not proof that an item is popular. Hacker News and
Lobsters engagement is read from their public JSON endpoints before selection.
The JSON sent to the summarizer contains selected candidates only; a daily
audit file keeps both selected and rejected candidates with the metrics
observed at run time.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo


HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
HN_MAX_AGE_HOURS = 36
HN_MIN_SCORE = 50
HN_MIN_COMMENTS = 20
HN_SELECTION_LIMIT = 5
LOBSTERS_API_URL = "https://lobste.rs/hottest.json"
LOBSTERS_MAX_AGE_HOURS = 48
LOBSTERS_MIN_SCORE = 30
LOBSTERS_MIN_COMMENTS = 10
LOBSTERS_SELECTION_LIMIT = 3

# These windows are deterministic freshness filters, not claims of popularity.
# The HN engagement threshold is intentionally called out as temporary in the
# emitted policy so it can be tuned after observing audit data.
SOURCE_POLICIES = {
    "geeknews": {"max_age_hours": 48, "selection_limit": 6},
    "lobsters": {
        "max_age_hours": LOBSTERS_MAX_AGE_HOURS,
        "selection_limit": LOBSTERS_SELECTION_LIMIT,
    },
    "reddit": {"max_age_hours": 48, "selection_limit": 4},
    "zdnet": {"max_age_hours": 36, "selection_limit": 3},
}

SOURCES = [
    {
        "key": "geeknews",
        "name": "GeekNews",
        "url": "https://news.hada.io/rss/news",
        "limit": 8,
    },
    {
        "key": "hacker_news",
        "name": "Hacker News",
        "url": "https://hnrss.org/frontpage",
        "limit": 30,
    },
    {
        "key": "lobsters",
        "name": "Lobsters",
        "url": LOBSTERS_API_URL,
        "limit": 25,
    },
    {
        "key": "reddit",
        "name": "Reddit r/technology",
        "url": "https://www.reddit.com/r/technology/.rss",
        "limit": 6,
    },
    {
        "key": "zdnet",
        "name": "ZDNet Korea",
        "url": "https://zdnet.co.kr/feed/",
        "limit": 5,
    },
]

SOURCE_KIND = {
    "reddit": "community_submission",
    "geeknews": "community_submission",
    "lobsters": "community_topic",
    "zdnet": "editorial_news",
}

SOURCE_SECTION = {
    "community_topic": "검증된 커뮤니티 화제",
    "community_submission": "커뮤니티 제출·큐레이션",
    "editorial_news": "편집 뉴스",
}

ATOM_NS = "http://www.w3.org/2005/Atom"


class _HTMLExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(unescape(href))


def strip_html(value):
    parser = _HTMLExtractor()
    parser.feed(value or "")
    parser.close()
    return " ".join(" ".join(parser.parts).split())


def html_links(value):
    parser = _HTMLExtractor()
    parser.feed(value or "")
    parser.close()
    return parser.links


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def parse_published_at(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def candidate_record(
    *,
    source,
    source_kind,
    title,
    published_at,
    article_url,
    discussion_url=None,
    summary="",
    metrics=None,
    evidence_level="title_only_no_engagement",
    selected=False,
    selection_reason="not_evaluated",
):
    """Return the common candidate schema used by output and audit files."""
    return {
        "source": source,
        "source_kind": source_kind,
        "section": SOURCE_SECTION[source_kind],
        "title": title,
        "published_at": iso_utc(published_at),
        "article_url": article_url,
        "discussion_url": discussion_url,
        "summary": summary[:600],
        "metrics": metrics or {},
        "evidence_level": evidence_level,
        "selected": bool(selected),
        "selection_reason": selection_reason,
    }


def _is_http_url(value):
    try:
        parsed = urllib.parse.urlparse(value or "")
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def canonical_article_url(value):
    """Normalize a public article URL for cross-source duplicate detection."""
    try:
        parsed = urllib.parse.urlsplit(value or "")
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    port = parsed.port
    if port and not (
        (parsed.scheme == "http" and port == 80)
        or (parsed.scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    tracking = {"fbclid", "gclid", "mc_cid", "mc_eid"}
    query = [
        (key, item)
        for key, item in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in tracking
    ]
    normalized_query = urllib.parse.urlencode(sorted(query))
    return urllib.parse.urlunsplit(("", host, path, normalized_query, ""))


def _reddit_article_url(raw_content, discussion_url):
    for link in html_links(raw_content):
        if not _is_http_url(link):
            continue
        host = urllib.parse.urlparse(link).netloc.lower()
        if not host.endswith("reddit.com") and "redd.it" not in host:
            return link
    return discussion_url


def normalize_rss_candidate(
    source, title, link, raw_summary, published_at, now=None
):
    """Normalize and deterministically select a non-HN RSS candidate."""
    now = now or utc_now()
    key = source["key"]
    source_kind = SOURCE_KIND[key]
    article_url = link
    discussion_url = None
    summary = strip_html(raw_summary)

    # Reddit Atom content is submission metadata, not article text or comment
    # substance. Preserve only the submitted title and locate the article URL.
    if key == "reddit":
        discussion_url = link
        article_url = _reddit_article_url(raw_summary, discussion_url)
        summary = ""

    evidence_level = (
        "feed_content_no_engagement" if summary else "title_only_no_engagement"
    )
    selected = True
    reason = "recent_feed_candidate"

    if not _is_http_url(article_url):
        selected = False
        reason = "missing_article_url"
    elif published_at is None:
        selected = False
        reason = "missing_published_at"
    else:
        age = now - published_at
        max_age = timedelta(hours=SOURCE_POLICIES[key]["max_age_hours"])
        if age > max_age:
            selected = False
            reason = f"older_than_{SOURCE_POLICIES[key]['max_age_hours']}h"
        elif age < timedelta(minutes=-5):
            selected = False
            reason = "published_at_in_future"

    return candidate_record(
        source=source["name"],
        source_kind=source_kind,
        title=title,
        published_at=published_at,
        article_url=article_url,
        discussion_url=discussion_url,
        summary=summary,
        metrics={},
        evidence_level=evidence_level,
        selected=selected,
        selection_reason=reason,
    )


def hn_item_id(link, raw_summary="", guid="", comments_url=""):
    for value in (comments_url, guid, raw_summary, link):
        match = re.search(r"news\.ycombinator\.com/item\?id=(\d+)", value or "")
        if match:
            return int(match.group(1))
    return None


def normalize_hn_candidate(discovered, api_item, now=None):
    """Apply the temporary HN age/engagement threshold to official metadata."""
    now = now or utc_now()
    item_id = discovered.get("hn_item_id")
    discussion_url = (
        f"https://news.ycombinator.com/item?id={item_id}" if item_id else None
    )
    title = discovered.get("title", "")
    article_url = discovered.get("article_url") or discussion_url
    published_at = discovered.get("published_at")
    metrics = {}
    selected = False

    if not isinstance(api_item, dict):
        reason = "official_hn_metadata_unavailable"
    elif api_item.get("deleted") or api_item.get("dead") or api_item.get("type") != "story":
        reason = "not_a_live_hn_story"
    else:
        item_id = api_item.get("id", item_id)
        discussion_url = f"https://news.ycombinator.com/item?id={item_id}"
        title = api_item.get("title") or title
        article_url = api_item.get("url") or discussion_url
        published_at = datetime.fromtimestamp(api_item.get("time", 0), timezone.utc)
        score = int(api_item.get("score") or 0)
        comments = int(api_item.get("descendants") or 0)
        metrics = {
            "score": score,
            "comments": comments,
            "observed_from": "hacker_news_official_api",
        }
        age = now - published_at
        if not _is_http_url(article_url):
            reason = "missing_article_url"
        elif age > timedelta(hours=HN_MAX_AGE_HOURS):
            reason = f"older_than_{HN_MAX_AGE_HOURS}h"
        elif age < timedelta(minutes=-5):
            reason = "published_at_in_future"
        elif score < HN_MIN_SCORE and comments < HN_MIN_COMMENTS:
            reason = (
                "below_temporary_hn_threshold: "
                f"score={score}<{HN_MIN_SCORE} and comments={comments}<{HN_MIN_COMMENTS}"
            )
        else:
            selected = True
            reason = (
                "meets_temporary_hn_threshold: "
                f"age<={HN_MAX_AGE_HOURS}h and "
                f"(score={score}>={HN_MIN_SCORE} or comments={comments}>={HN_MIN_COMMENTS})"
            )

    return candidate_record(
        source="Hacker News",
        source_kind="community_topic" if metrics else "community_submission",
        title=title,
        published_at=published_at,
        article_url=article_url,
        discussion_url=discussion_url,
        summary="",
        metrics=metrics,
        evidence_level=(
            "official_metrics_title_only_no_comment_text"
            if metrics
            else "title_only_no_engagement"
        ),
        selected=selected,
        selection_reason=reason,
    )


def normalize_lobsters_candidate(item, now=None):
    """Apply a temporary age/engagement threshold to Lobsters metadata."""
    now = now or utc_now()
    if not isinstance(item, dict):
        return candidate_record(
            source="Lobsters",
            source_kind="community_submission",
            title="",
            published_at=None,
            article_url=None,
            selected=False,
            selection_reason="invalid_lobsters_record",
        )

    title = str(item.get("title") or "").strip()
    published_at = parse_published_at(str(item.get("created_at") or ""))
    discussion_url = item.get("comments_url") or item.get("short_id_url")
    article_url = item.get("url") or item.get("short_id_url") or discussion_url
    try:
        score = int(item.get("score") or 0)
        comments = int(item.get("comment_count") or 0)
    except (TypeError, ValueError):
        score = 0
        comments = 0
    tags = [tag for tag in (item.get("tags") or []) if isinstance(tag, str)]
    metrics = {
        "score": score,
        "comments": comments,
        "tags": tags,
        "observed_from": "lobsters_hottest_json",
    }
    selected = False

    if not title:
        reason = "missing_title"
    elif not _is_http_url(article_url):
        reason = "missing_article_url"
    elif not _is_http_url(discussion_url):
        reason = "missing_discussion_url"
    elif published_at is None:
        reason = "missing_published_at"
    else:
        age = now - published_at
        if age > timedelta(hours=LOBSTERS_MAX_AGE_HOURS):
            reason = f"older_than_{LOBSTERS_MAX_AGE_HOURS}h"
        elif age < timedelta(minutes=-5):
            reason = "published_at_in_future"
        elif score < LOBSTERS_MIN_SCORE and comments < LOBSTERS_MIN_COMMENTS:
            reason = (
                "below_temporary_lobsters_threshold: "
                f"score={score}<{LOBSTERS_MIN_SCORE} and "
                f"comments={comments}<{LOBSTERS_MIN_COMMENTS}"
            )
        else:
            selected = True
            reason = (
                "meets_temporary_lobsters_threshold: "
                f"age<={LOBSTERS_MAX_AGE_HOURS}h and "
                f"(score={score}>={LOBSTERS_MIN_SCORE} or "
                f"comments={comments}>={LOBSTERS_MIN_COMMENTS})"
            )

    return candidate_record(
        source="Lobsters",
        source_kind="community_topic",
        title=title,
        published_at=published_at,
        article_url=article_url,
        discussion_url=discussion_url,
        summary="",
        metrics=metrics,
        evidence_level="source_metrics_title_only_no_comment_text",
        selected=selected,
        selection_reason=reason,
    )


def _request_bytes(url, timeout=12):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; NewsBot/2.0)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_json(url):
    return json.loads(_request_bytes(url))


def _rss_text(element, *names):
    for name in names:
        value = element.findtext(name)
        if value:
            return value.strip()
    return ""


def discover_rss(source):
    try:
        raw = _request_bytes(source["url"])
    except Exception as exc:
        return [], f"{source['name']}: fetch error — {exc}"

    try:
        root = ET.fromstring(raw)
    except Exception as exc:
        return [], f"{source['name']}: parse error — {exc}"

    discovered = []
    for item in root.findall(".//item"):
        if len(discovered) >= source["limit"]:
            break
        title = _rss_text(item, "title")
        link = _rss_text(item, "link")
        if not title or not link:
            continue
        discovered.append(
            {
                "title": title,
                "article_url": link,
                "raw_summary": _rss_text(item, "description"),
                "published_at": parse_published_at(_rss_text(item, "pubDate")),
                "guid": _rss_text(item, "guid"),
                "comments_url": _rss_text(item, "comments"),
            }
        )

    if not discovered:
        for entry in root.findall(f".//{{{ATOM_NS}}}entry"):
            if len(discovered) >= source["limit"]:
                break
            title = _rss_text(entry, f"{{{ATOM_NS}}}title")
            link = ""
            for link_element in entry.findall(f"{{{ATOM_NS}}}link"):
                if link_element.get("rel", "alternate") == "alternate":
                    link = (link_element.get("href") or "").strip()
                    if link:
                        break
            if not title or not link:
                continue
            discovered.append(
                {
                    "title": title,
                    "article_url": link,
                    "raw_summary": _rss_text(
                        entry,
                        f"{{{ATOM_NS}}}content",
                        f"{{{ATOM_NS}}}summary",
                    ),
                    "published_at": parse_published_at(
                        _rss_text(
                            entry,
                            f"{{{ATOM_NS}}}published",
                            f"{{{ATOM_NS}}}updated",
                        )
                    ),
                    "guid": _rss_text(entry, f"{{{ATOM_NS}}}id"),
                    "comments_url": "",
                }
            )

    if not discovered:
        return [], f"{source['name']}: no candidates (feed structure may have changed)"
    return discovered, None


def discover_lobsters(source):
    try:
        payload = fetch_json(source["url"])
    except Exception as exc:
        return [], f"{source['name']}: fetch error — {exc}"
    if not isinstance(payload, list):
        return [], f"{source['name']}: invalid JSON contract"
    discovered = [
        item for item in payload[: source["limit"]] if isinstance(item, dict)
    ]
    if not discovered:
        return [], f"{source['name']}: no candidates (JSON contract may have changed)"
    return discovered, None


def _fetch_hn_api_item(item_id):
    try:
        return fetch_json(f"{HN_API_BASE}/item/{item_id}.json")
    except Exception:
        return None


def collect_candidates(now=None):
    now = now or utc_now()
    candidates = []
    errors = []

    for source in SOURCES:
        if source["key"] == "lobsters":
            discovered, error = discover_lobsters(source)
            if error:
                errors.append(error)
                continue
            candidates.extend(
                normalize_lobsters_candidate(item, now) for item in discovered
            )
            continue

        discovered, error = discover_rss(source)
        if error:
            errors.append(error)
            continue

        if source["key"] == "hacker_news":
            hn_discovered = []
            for item in discovered:
                item["hn_item_id"] = hn_item_id(
                    item["article_url"],
                    item["raw_summary"],
                    item["guid"],
                    item["comments_url"],
                )
                hn_discovered.append(item)
            ids = [item["hn_item_id"] for item in hn_discovered]
            with ThreadPoolExecutor(max_workers=8) as executor:
                api_items = list(executor.map(_fetch_hn_api_item, ids))
            candidates.extend(
                normalize_hn_candidate(item, api_item, now)
                for item, api_item in zip(hn_discovered, api_items)
            )
            continue

        candidates.extend(
            normalize_rss_candidate(
                source,
                item["title"],
                item["article_url"],
                item["raw_summary"],
                item["published_at"],
                now,
            )
            for item in discovered
        )

    apply_cross_source_deduplication(candidates)
    apply_selection_limits(candidates)
    return candidates, errors


def apply_cross_source_deduplication(candidates):
    """Keep the first eligible source for each normalized article URL."""
    seen = {}
    for candidate in candidates:
        if not candidate["selected"]:
            continue
        canonical = canonical_article_url(candidate.get("article_url"))
        if not canonical:
            continue
        first_source = seen.get(canonical)
        if first_source is None:
            seen[canonical] = candidate["source"]
            continue
        candidate["selected"] = False
        candidate["selection_reason"] = (
            f"duplicate_article_url:first_source={first_source}"
        )


def apply_selection_limits(candidates):
    """Cap eligible feed-order results without relaxing any source criteria."""
    limits = {"Hacker News": HN_SELECTION_LIMIT}
    limits.update(
        {
            source["name"]: SOURCE_POLICIES[source["key"]]["selection_limit"]
            for source in SOURCES
            if source["key"] in SOURCE_POLICIES
        }
    )
    eligible_seen = Counter()
    for candidate in candidates:
        if not candidate["selected"]:
            continue
        source_name = candidate["source"]
        eligible_seen[source_name] += 1
        limit = limits[source_name]
        if eligible_seen[source_name] <= limit:
            continue
        candidate["selected"] = False
        candidate["selection_reason"] = (
            "eligible_but_over_source_limit: "
            f"eligible_rank={eligible_seen[source_name]} limit={limit}"
        )


def selection_policy():
    return {
        "rss_role": "candidate_discovery_only",
        "force_target_count": False,
        "selection_order": "observed_feed_order_after_source_criteria",
        "cross_source_deduplication": (
            "normalized_article_url_first_eligible_source_wins"
        ),
        "hacker_news": {
            "metrics_source": "official_api",
            "max_age_hours": HN_MAX_AGE_HOURS,
            "min_score": HN_MIN_SCORE,
            "min_comments": HN_MIN_COMMENTS,
            "logic": "age <= max_age AND (score >= min_score OR comments >= min_comments)",
            "temporary_threshold": True,
            "selection_limit": HN_SELECTION_LIMIT,
        },
        "lobsters": {
            "metrics_source": "public_hottest_json",
            "max_age_hours": LOBSTERS_MAX_AGE_HOURS,
            "min_score": LOBSTERS_MIN_SCORE,
            "min_comments": LOBSTERS_MIN_COMMENTS,
            "logic": "age <= max_age AND (score >= min_score OR comments >= min_comments)",
            "temporary_threshold": True,
            "selection_limit": LOBSTERS_SELECTION_LIMIT,
        },
        "other_source_freshness_hours": {
            key: value["max_age_hours"] for key, value in SOURCE_POLICIES.items()
        },
        "other_source_selection_limits": {
            key: value["selection_limit"] for key, value in SOURCE_POLICIES.items()
        },
        "community_claims": (
            "Only official/reliable metrics permit quantified popularity claims; "
            "comment sentiment requires collected comment text."
        ),
    }


def selection_summary(candidates):
    def reason_code(candidate):
        return candidate["selection_reason"].split(":", 1)[0]

    return {
        "candidate_count": len(candidates),
        "selected_count": sum(item["selected"] for item in candidates),
        "selected_by_source_kind": dict(
            sorted(
                Counter(
                    item["source_kind"] for item in candidates if item["selected"]
                ).items()
            )
        ),
        "excluded_by_reason": dict(
            sorted(
                Counter(
                    reason_code(item)
                    for item in candidates
                    if not item["selected"]
                ).items()
            )
        ),
    }


def default_audit_dir():
    return Path.home() / "Library" / "Application Support" / "chumji-news" / "trend-audit"


def write_daily_audit(audit_dir, collected_at, candidates, errors):
    audit_dir = Path(audit_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_date = collected_at.astimezone(ZoneInfo("Asia/Seoul")).date().isoformat()
    audit_path = audit_dir / f"{audit_date}.json"
    daily = {"schema_version": 1, "date": audit_date, "runs": []}
    if audit_path.exists():
        try:
            existing = json.loads(audit_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"refusing to replace unreadable audit file: {audit_path}") from exc
        if not (
            existing.get("schema_version") == 1
            and existing.get("date") == audit_date
            and isinstance(existing.get("runs"), list)
        ):
            raise ValueError(f"refusing to replace incompatible audit file: {audit_path}")
        daily = existing

    daily["runs"].append(
        {
            "collected_at": iso_utc(collected_at),
            "selection_policy": selection_policy(),
            "summary": selection_summary(candidates),
            "errors": errors,
            "candidates": candidates,
        }
    )

    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{audit_date}.", suffix=".tmp", dir=audit_dir
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as output:
            json.dump(daily, output, ensure_ascii=False, indent=2)
            output.write("\n")
        os.replace(temp_name, audit_path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return audit_path


def build_output(collected_at, candidates, errors):
    selected = [item for item in candidates if item["selected"]]
    return {
        "schema_version": 2,
        "collected_at": iso_utc(collected_at),
        "selection_policy": selection_policy(),
        "selection_summary": selection_summary(candidates),
        "errors": errors,
        # This is the only candidate list passed to the LLM.
        "articles": selected,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=default_audit_dir(),
        help="directory for date-partitioned candidate audit JSON",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    collected_at = utc_now()
    candidates, errors = collect_candidates(collected_at)
    try:
        audit_path = write_daily_audit(
            args.audit_dir, collected_at, candidates, errors
        )
    except Exception as exc:
        print(f"audit write failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(build_output(collected_at, candidates, errors), ensure_ascii=False, indent=2))
    print(f"audit: {audit_path}", file=sys.stderr)
    if errors:
        print(f"warning: {len(errors)} source collection failure(s)", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
