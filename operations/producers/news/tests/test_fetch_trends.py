import importlib.util
import json
import pathlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone


MODULE_PATH = pathlib.Path(__file__).parents[1] / "fetch_trends.py"
SPEC = importlib.util.spec_from_file_location("fetch_trends", MODULE_PATH)
fetch_trends = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_trends)

NOW = datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc)

GITHUB_TRENDING_HTML = b"""
<article class="Box-row">
  <h2><a href="/general/photo-app">general / photo-app</a></h2>
  <p>A photo sharing application</p>
  <span itemprop="programmingLanguage">Ruby</span>
  <span>9,999 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/dev/agent-kit">dev / agent-kit</a></h2>
  <p>AI coding agent workflow toolkit</p>
  <span itemprop="programmingLanguage">Python</span>
  <span>1,234 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/infra/mcp-server">infra / mcp-server</a></h2>
  <p>MCP developer tool server</p>
  <span itemprop="programmingLanguage">Rust</span>
  <span>800 stars today</span>
</article>
<article class="Box-row">
  <h2><a href="/tools/terminal-cli">tools / terminal-cli</a></h2>
  <p>Developer terminal workflow</p>
  <span itemprop="programmingLanguage">Go</span>
  <span>700 stars today</span>
</article>
"""


def source(key):
    return next(item for item in fetch_trends.SOURCES if item["key"] == key)


class GitHubTrendingSelectionTest(unittest.TestCase):
    def test_focus_then_stars_then_page_rank_and_limit(self):
        records = fetch_trends.parse_github_trending(
            GITHUB_TRENDING_HTML, source("github_trending")
        )

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["repository"], "dev/agent-kit")
        self.assertNotIn("general/photo-app", [item["repository"] for item in records])

        candidate = fetch_trends.normalize_github_candidate(records[0])
        self.assertTrue(candidate["selected"])
        self.assertEqual(candidate["source_kind"], "repository_trending")
        self.assertEqual(candidate["metrics"]["stars_today"], 1234)
        self.assertEqual(candidate["metrics"]["daily_rank"], 2)
        self.assertEqual(
            candidate["evidence_level"],
            "source_metrics_repository_description",
        )

    def test_layout_failure_is_isolated(self):
        with self.assertRaisesRegex(ValueError, "no GitHub Trending"):
            fetch_trends.parse_github_trending(
                b"<html></html>", source("github_trending")
            )


class HackerNewsSelectionTest(unittest.TestCase):
    def discovered(self, title, item_id):
        return {
            "title": title,
            "hn_item_id": item_id,
            "article_url": f"https://example.com/{item_id}",
            "published_at": NOW - timedelta(hours=1),
        }

    def api_item(self, title, item_id, score, comments, age_hours=1):
        return {
            "id": item_id,
            "type": "story",
            "title": title,
            "url": f"https://example.com/{item_id}",
            "time": int((NOW - timedelta(hours=age_hours)).timestamp()),
            "score": score,
            "descendants": comments,
        }

    def test_openlogi_is_selected_without_inventing_semantics(self):
        candidate = fetch_trends.normalize_hn_candidate(
            self.discovered("OpenLogi", 49355606),
            self.api_item("OpenLogi", 49355606, 460, 123),
            NOW,
        )

        self.assertTrue(candidate["selected"])
        self.assertEqual(candidate["source_kind"], "community_topic")
        self.assertEqual(candidate["summary"], "")
        self.assertEqual(
            candidate["evidence_level"],
            "official_metrics_title_only_no_comment_text",
        )
        self.assertEqual(candidate["metrics"]["score"], 460)
        self.assertEqual(
            candidate["discussion_url"],
            "https://news.ycombinator.com/item?id=49355606",
        )
        self.assertNotIn("logistics", json.dumps(candidate).lower())

    def test_the_integer_below_threshold_is_excluded(self):
        candidate = fetch_trends.normalize_hn_candidate(
            self.discovered("The Integer", 49350000),
            self.api_item("The Integer", 49350000, 19, 2),
            NOW,
        )

        self.assertFalse(candidate["selected"])
        self.assertEqual(candidate["metrics"]["score"], 19)
        self.assertEqual(candidate["metrics"]["comments"], 2)
        self.assertIn("below_temporary_hn_threshold", candidate["selection_reason"])

    def test_score_or_comments_can_meet_threshold(self):
        score_selected = fetch_trends.normalize_hn_candidate(
            self.discovered("Score route", 1),
            self.api_item("Score route", 1, 50, 0),
            NOW,
        )
        comments_selected = fetch_trends.normalize_hn_candidate(
            self.discovered("Comment route", 2),
            self.api_item("Comment route", 2, 1, 20),
            NOW,
        )

        self.assertTrue(score_selected["selected"])
        self.assertTrue(comments_selected["selected"])

    def test_old_story_is_excluded_even_with_engagement(self):
        candidate = fetch_trends.normalize_hn_candidate(
            self.discovered("Old story", 3),
            self.api_item("Old story", 3, 500, 200, age_hours=37),
            NOW,
        )

        self.assertFalse(candidate["selected"])
        self.assertEqual(candidate["selection_reason"], "older_than_36h")


class LobstersSelectionTest(unittest.TestCase):
    def item(
        self, score=30, comments=0, age_hours=1, url="https://example.com/story"
    ):
        return {
            "short_id": "abc123",
            "created_at": (NOW - timedelta(hours=age_hours)).isoformat(),
            "title": "A careful systems article",
            "url": url,
            "score": score,
            "comment_count": comments,
            "tags": ["programming", "systems"],
            "short_id_url": "https://lobste.rs/s/abc123",
            "comments_url": "https://lobste.rs/s/abc123/a_careful_systems_article",
        }

    def test_score_or_comments_can_meet_threshold(self):
        score_selected = fetch_trends.normalize_lobsters_candidate(
            self.item(score=30, comments=0), NOW
        )
        comments_selected = fetch_trends.normalize_lobsters_candidate(
            self.item(score=1, comments=10), NOW
        )

        self.assertTrue(score_selected["selected"])
        self.assertTrue(comments_selected["selected"])
        self.assertEqual(score_selected["source_kind"], "community_topic")
        self.assertEqual(
            score_selected["evidence_level"],
            "source_metrics_title_only_no_comment_text",
        )
        self.assertEqual(score_selected["metrics"]["tags"], ["programming", "systems"])

    def test_low_engagement_and_old_items_are_excluded(self):
        low = fetch_trends.normalize_lobsters_candidate(
            self.item(score=29, comments=9), NOW
        )
        old = fetch_trends.normalize_lobsters_candidate(
            self.item(score=100, comments=50, age_hours=49), NOW
        )

        self.assertFalse(low["selected"])
        self.assertIn("below_temporary_lobsters_threshold", low["selection_reason"])
        self.assertFalse(old["selected"])
        self.assertEqual(old["selection_reason"], "older_than_48h")

    def test_text_post_uses_lobsters_story_as_article_url(self):
        candidate = fetch_trends.normalize_lobsters_candidate(
            self.item(url="", score=100), NOW
        )

        self.assertTrue(candidate["selected"])
        self.assertEqual(candidate["article_url"], "https://lobste.rs/s/abc123")


class SourceClassificationTest(unittest.TestCase):
    def test_source_mix_and_order_match_editorial_policy(self):
        self.assertEqual(
            [item["key"] for item in fetch_trends.SOURCES],
            [
                "github_trending",
                "geeknews",
                "hacker_news",
                "lobsters",
                "reddit",
                "zdnet",
            ],
        )
        self.assertEqual(fetch_trends.GITHUB_SELECTION_LIMIT, 3)
        self.assertEqual(fetch_trends.HN_SELECTION_LIMIT, 5)
        self.assertEqual(fetch_trends.LOBSTERS_SELECTION_LIMIT, 3)
        self.assertEqual(
            {
                key: value["selection_limit"]
                for key, value in fetch_trends.SOURCE_POLICIES.items()
            },
            {"geeknews": 6, "lobsters": 3, "reddit": 4, "zdnet": 3},
        )

    def test_geeknews_is_classified_as_curated_submission(self):
        candidate = fetch_trends.normalize_rss_candidate(
            source("geeknews"),
            "개발 도구 소개",
            "https://news.hada.io/topic?id=1",
            "<p>도구 설명</p>",
            NOW - timedelta(hours=2),
            NOW,
        )

        self.assertTrue(candidate["selected"])
        self.assertEqual(candidate["source_kind"], "community_submission")
        self.assertEqual(candidate["section"], "커뮤니티 제출·큐레이션")
        self.assertEqual(candidate["metrics"], {})

    def test_reddit_without_metrics_is_not_called_community_topic(self):
        raw_content = """
        <p><a href="https://example.com/article">Article</a></p>
        <p><a href="https://www.reddit.com/r/technology/comments/abc">comments</a></p>
        """
        candidate = fetch_trends.normalize_rss_candidate(
            source("reddit"),
            "Example submission",
            "https://www.reddit.com/r/technology/comments/abc",
            raw_content,
            NOW - timedelta(hours=2),
            NOW,
        )

        self.assertTrue(candidate["selected"])
        self.assertEqual(candidate["source_kind"], "community_submission")
        self.assertEqual(candidate["article_url"], "https://example.com/article")
        self.assertEqual(candidate["summary"], "")
        self.assertEqual(candidate["metrics"], {})
        self.assertEqual(candidate["evidence_level"], "title_only_no_engagement")

    def test_zdnet_is_editorial_news(self):
        zdnet = fetch_trends.normalize_rss_candidate(
            source("zdnet"),
            "편집 기사",
            "https://zdnet.co.kr/view/?no=1",
            "기사 요약",
            NOW - timedelta(hours=1),
            NOW,
        )
        self.assertEqual(zdnet["source_kind"], "editorial_news")


class CandidateSchemaAndAuditTest(unittest.TestCase):
    def test_cross_source_duplicate_keeps_first_eligible_source(self):
        first = fetch_trends.normalize_hn_candidate(
            {
                "title": "Shared article",
                "hn_item_id": 100,
                "article_url": "https://example.com/story?utm_source=hn",
                "published_at": NOW,
            },
            {
                "id": 100,
                "type": "story",
                "title": "Shared article",
                "url": "https://example.com/story?utm_source=hn",
                "time": int(NOW.timestamp()),
                "score": 100,
                "descendants": 50,
            },
            NOW,
        )
        duplicate = fetch_trends.normalize_lobsters_candidate(
            {
                "created_at": NOW.isoformat(),
                "title": "Shared article on Lobsters",
                "url": "http://EXAMPLE.com/story/#discussion",
                "score": 100,
                "comment_count": 50,
                "tags": ["programming"],
                "short_id_url": "https://lobste.rs/s/duplicate",
                "comments_url": "https://lobste.rs/s/duplicate/shared_article",
            },
            NOW,
        )

        fetch_trends.apply_cross_source_deduplication([first, duplicate])

        self.assertTrue(first["selected"])
        self.assertFalse(duplicate["selected"])
        self.assertEqual(
            duplicate["selection_reason"],
            "duplicate_article_url:first_source=Hacker News",
        )

    def test_source_limits_do_not_promote_or_force_candidates(self):
        candidates = []
        for index in range(6):
            candidates.append(
                fetch_trends.normalize_rss_candidate(
                    source("reddit"),
                    f"Submission {index}",
                    f"https://example.com/{index}",
                    '<a href="https://example.com/article">article</a>',
                    NOW - timedelta(hours=index),
                    NOW,
                )
            )
        already_excluded = fetch_trends.normalize_rss_candidate(
            source("reddit"),
            "Old submission",
            "https://example.com/old",
            '<a href="https://example.com/old-article">article</a>',
            NOW - timedelta(hours=60),
            NOW,
        )
        candidates.append(already_excluded)

        fetch_trends.apply_selection_limits(candidates)

        self.assertEqual(sum(item["selected"] for item in candidates), 4)
        self.assertIn("eligible_but_over_source_limit", candidates[4]["selection_reason"])
        self.assertEqual(candidates[-1]["selection_reason"], "older_than_48h")

    def test_common_schema_and_selected_only_model_output(self):
        selected = fetch_trends.normalize_rss_candidate(
            source("geeknews"),
            "Selected",
            "https://example.com/selected",
            "summary",
            NOW - timedelta(hours=1),
            NOW,
        )
        excluded = fetch_trends.normalize_rss_candidate(
            source("geeknews"),
            "Excluded",
            "https://example.com/excluded",
            "summary",
            NOW - timedelta(hours=60),
            NOW,
        )
        required = {
            "source_kind",
            "published_at",
            "article_url",
            "discussion_url",
            "metrics",
            "evidence_level",
            "selected",
            "selection_reason",
        }

        self.assertTrue(required.issubset(selected))
        output = fetch_trends.build_output(NOW, [selected, excluded], [])
        self.assertEqual([item["title"] for item in output["articles"]], ["Selected"])
        self.assertTrue(output["selection_policy"]["hacker_news"]["temporary_threshold"])
        self.assertTrue(output["selection_policy"]["lobsters"]["temporary_threshold"])
        self.assertEqual(
            output["selection_policy"]["github_trending"]["selection_limit"], 3
        )
        self.assertIn("normalized_article_url", output["selection_policy"]["cross_source_deduplication"])
        self.assertFalse(output["selection_policy"]["force_target_count"])

    def test_daily_audit_appends_run_snapshots(self):
        candidate = fetch_trends.normalize_rss_candidate(
            source("geeknews"),
            "개발 도구 소개",
            "https://news.hada.io/topic?id=1",
            "summary",
            NOW - timedelta(hours=1),
            NOW,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = fetch_trends.write_daily_audit(directory, NOW, [candidate], [])
            fetch_trends.write_daily_audit(
                directory, NOW + timedelta(minutes=5), [candidate], []
            )
            audit = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(audit["date"], "2026-08-19")
        self.assertEqual(len(audit["runs"]), 2)
        self.assertEqual(audit["runs"][0]["candidates"][0]["title"], "개발 도구 소개")

    def test_selection_summary_groups_metric_details_by_reason_code(self):
        first = fetch_trends.normalize_hn_candidate(
            {
                "title": "Low one",
                "hn_item_id": 10,
                "article_url": "https://example.com/10",
                "published_at": NOW,
            },
            {
                "id": 10,
                "type": "story",
                "title": "Low one",
                "url": "https://example.com/10",
                "time": int(NOW.timestamp()),
                "score": 19,
                "descendants": 2,
            },
            NOW,
        )
        second = fetch_trends.normalize_hn_candidate(
            {
                "title": "Low two",
                "hn_item_id": 11,
                "article_url": "https://example.com/11",
                "published_at": NOW,
            },
            {
                "id": 11,
                "type": "story",
                "title": "Low two",
                "url": "https://example.com/11",
                "time": int(NOW.timestamp()),
                "score": 3,
                "descendants": 1,
            },
            NOW,
        )

        summary = fetch_trends.selection_summary([first, second])

        self.assertEqual(
            summary["excluded_by_reason"]["below_temporary_hn_threshold"], 2
        )


if __name__ == "__main__":
    unittest.main()
