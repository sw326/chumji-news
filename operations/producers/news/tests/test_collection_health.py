import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from operations.producers.news import fetch_trends as collector
from operations.producers.news.trend_briefing import add_notice


ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 30, 0, tzinfo=timezone.utc)


def collected(kind):
    """Exercise the real selection/health aggregation without network or receipts."""
    def rss(source):
        if kind == "failed" or (kind == "degraded" and source["key"] == "hacker_news"):
            return [], source["name"] + ": fixture failure"
        if kind != "empty" and source["key"] == "geeknews":
            return [{"title": "Available story", "article_url": "https://example.test/article",
                     "raw_summary": "Source text", "published_at": NOW}], None
        return [], None

    with (patch.object(collector, "read_recent_published_repositories", return_value=set()),
          patch.object(collector, "discover_github_trending", return_value=([], "GitHub failed" if kind == "failed" else None)),
          patch.object(collector, "discover_lobsters", return_value=([], "Lobsters failed" if kind == "failed" else None)),
          patch.object(collector, "discover_rss", side_effect=rss)):
        return collector.collect_candidates(NOW)


def payload_for(kind):
    candidates, errors, health = collected(kind)
    return collector.build_output(NOW, candidates, errors, health)


class CollectionHealthTests(unittest.TestCase):
    def test_four_states_preserve_selection_counts(self):
        for kind in ("ok", "empty", "degraded", "failed"):
            with self.subTest(kind=kind):
                payload = payload_for(kind)
                health = payload["collection_health"]
                self.assertEqual(health["status"], kind)
                self.assertEqual(len(health["sources"]), len(collector.SOURCES))
                self.assertEqual(sum(s["selected_count"] for s in health["sources"]), len(payload["articles"]))
                self.assertEqual(len(payload["articles"]), int(kind in {"ok", "degraded"}))

    def test_valid_empty_feeds_are_not_layout_failures(self):
        source = next(s for s in collector.SOURCES if s["key"] == "geeknews")
        for body in (b"<rss><channel/></rss>", b'<feed xmlns="http://www.w3.org/2005/Atom"/>'):
            with patch.object(collector, "_request_bytes", return_value=body):
                self.assertEqual(collector.discover_rss(source), ([], None))
        for body in (b"<html/>", b"<rss><channel><item/></channel></rss>", b"broken"):
            with patch.object(collector, "_request_bytes", return_value=body):
                self.assertIsNotNone(collector.discover_rss(source)[1])
        with patch.object(collector, "fetch_json", return_value=[]):
            self.assertEqual(collector.discover_lobsters(source), ([], None))
        with patch.object(collector, "fetch_json", return_value=[None]):
            self.assertIsNotNone(collector.discover_lobsters(source)[1])

    def test_hn_metadata_failures_are_not_empty_selection(self):
        source = next(s for s in collector.SOURCES if s["key"] == "hacker_news")
        discovered = [{"title": "story", "article_url": f"https://example.test/{i}",
                       "raw_summary": "", "guid": f"https://news.ycombinator.com/item?id={i}",
                       "comments_url": "", "published_at": NOW} for i in (1, 2)]
        story = {"id": 1, "type": "story", "time": NOW.timestamp(), "score": 100,
                 "title": "Available", "url": "https://example.test/1"}
        for api_items, expected in (([story, None], "degraded"), ([None, None], "failed")):
            with (self.subTest(expected=expected), patch.object(collector, "SOURCES", [source]),
                  patch.object(collector, "read_recent_published_repositories", return_value=set()),
                  patch.object(collector, "discover_rss", return_value=(discovered, None)),
                  patch.object(collector, "_fetch_hn_api_item", side_effect=api_items)):
                candidates, errors, health = collector.collect_candidates(NOW)
                self.assertEqual(health["status"], expected)
                self.assertTrue(errors)
                self.assertEqual(health["sources"][0]["failed_items"], api_items.count(None))

    def test_successful_hn_query_below_threshold_is_empty_not_failure(self):
        source = next(s for s in collector.SOURCES if s["key"] == "hacker_news")
        discovered = [{"title": "quiet story", "article_url": "https://example.test/quiet",
                       "raw_summary": "", "guid": "https://news.ycombinator.com/item?id=1",
                       "comments_url": "", "published_at": NOW}]
        story = {"id": 1, "type": "story", "time": NOW.timestamp(), "score": 1,
                 "title": "quiet story", "url": "https://example.test/quiet"}
        with (patch.object(collector, "SOURCES", [source]),
              patch.object(collector, "read_recent_published_repositories", return_value=set()),
              patch.object(collector, "discover_rss", return_value=(discovered, None)),
              patch.object(collector, "_fetch_hn_api_item", return_value=story)):
            candidates, errors, health = collector.collect_candidates(NOW)
        self.assertEqual(errors, [])
        self.assertEqual(health["status"], "empty")
        self.assertEqual(health["sources"][0]["candidate_count"], 1)
        self.assertEqual(health["sources"][0]["selected_count"], 0)

    def test_total_failure_writes_audit_and_json_before_nonzero_exit(self):
        result = collected("failed")
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with (patch.object(collector, "collect_candidates", return_value=result),
                  patch.object(collector, "utc_now", return_value=NOW),
                  contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO())):
                self.assertEqual(collector.main(["--audit-dir", directory]), 1)
            self.assertEqual(json.loads(output.getvalue())["collection_health"]["status"], "failed")
            audit = json.loads((Path(directory) / "2026-09-30.json").read_text())
            self.assertEqual(audit["runs"][0]["collection_health"], result[2])

    def test_notice_is_deterministic_and_idempotent(self):
        payload = payload_for("degraded")
        text = add_notice("Title\n\nBody\n", payload)
        self.assertIn("수집 안내: Hacker News 미수집", text)
        self.assertEqual(text, add_notice(text, payload))
        self.assertEqual(add_notice("Title\nBody", payload_for("ok")), "Title\nBody")


class TrendPipelineTests(unittest.TestCase):
    def run_pipeline(self, kind, *, collector_exit=0, summary=None, payload=None, mode="--publish", profile="trend"):
        """Real shell/prompt/health helper; collector, model and publisher are fakes.

        Dummy credential files exist only inside this temporary test tree.
        No production adapter, network, account, or receipt store is accessed.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT, root / "news", ignore=shutil.ignore_patterns("__pycache__"))
            news = root / "news"
            payload = payload if payload is not None else payload_for(kind)
            fetcher = {"trend": "fetch_trends.py", "morning": "fetch_morning_news.py", "it": "fetch_it_tech.py"}[profile]
            (news / fetcher).write_text(f"import sys\nprint({json.dumps(payload)!r})\nsys.exit({collector_exit})\n")
            summary = summary if summary is not None else "Title\n\n**Available story**\n" + "Source-backed summary. " * 60
            (news / "adapters/openclaw_gpt_summarize.sh").write_text(
                "#!/usr/bin/env python3\nfrom pathlib import Path\n"
                f"Path({str(root / 'model-called')!r}).touch()\nprint({summary!r})\n")
            (news / "adapters/publish.py").write_text(
                "import sys\nfrom pathlib import Path\n"
                f"Path({str(root / 'published.md')!r}).write_text(Path(sys.argv[sys.argv.index('--briefing-file') + 1]).read_text())\n")
            (root / "dummy.env").write_text("NEXT_PUBLIC_SUPABASE_URL=https://example.test\nSUPABASE_SERVICE_ROLE_KEY=fixture-only\n")
            (root / "dummy-token").write_text("fixture-only")
            env = os.environ | {"CHUMJI_NEWS_LOG_DIR": str(root / "logs"),
                                "CHUMJI_NEWS_RECEIPT_DIR": str(root / "receipts"),
                                "CHUMJI_NEWS_SUPABASE_ENV": str(root / "dummy.env"),
                                "CHUMJI_NEWS_TELEGRAM_TOKEN_FILE": str(root / "dummy-token")}
            result = subprocess.run([news / "run_profile.sh", profile, mode], env=env,
                                    text=True, capture_output=True, timeout=20)
            published = root / "published.md"
            return result, (root / "model-called").exists(), published.read_text() if published.exists() else None

    def test_normal_and_partial_failure_reach_publisher_with_correct_body(self):
        for kind in ("ok", "degraded"):
            with self.subTest(kind=kind):
                result, model_called, body = self.run_pipeline(kind)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(model_called)
                self.assertEqual("수집 안내:" in body, kind == "degraded")
                if kind == "degraded":
                    self.assertIn("Hacker News 미수집", body)
                    self.assertLess(body.index("수집 안내:"), body.index("Available story"))

    def test_zero_selected_publishes_empty_notice_without_model(self):
        for kind in ("empty", "degraded"):
            payload = payload_for(kind)
            payload["articles"] = []
            for source in payload["collection_health"]["sources"]:
                source["selected_count"] = 0
                if source["status"] == "ok":
                    source["status"] = "empty"
            result, model_called, body = self.run_pipeline(kind, payload=payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(model_called)
            self.assertIn("선정 기준을 충족한 기사가 없습니다", body)
            self.assertEqual("수집 안내:" in body, kind == "degraded")

    def test_total_failure_blocks_model_and_publication_even_if_collector_returns_zero(self):
        for exit_code in (0, 1):
            result, model_called, body = self.run_pipeline("failed", collector_exit=exit_code)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(model_called)
            self.assertIsNone(body)

    def test_missing_health_is_blocked_before_model(self):
        result, model_called, body = self.run_pipeline("ok", payload={"articles": []})
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(model_called)
        self.assertIsNone(body)

    def test_quality_notice_cannot_pad_short_model_output_past_guard(self):
        result, model_called, body = self.run_pipeline("degraded", summary="Title\n" + "x" * 160)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(model_called)
        self.assertIsNone(body)
        self.assertIn("briefing too short", result.stderr)

    def test_dry_run_does_not_invoke_publisher(self):
        result, model_called, body = self.run_pipeline("degraded", mode="--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(model_called)
        self.assertIsNone(body)
        self.assertEqual(json.loads(result.stdout)["category"], "trend")

    def test_morning_and_it_do_not_require_trend_health(self):
        for profile in ("morning", "it"):
            result, model_called, body = self.run_pipeline("ok", payload={"articles": []}, profile=profile)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(model_called)
            self.assertNotIn("수집 안내:", body)


if __name__ == "__main__":
    unittest.main()
