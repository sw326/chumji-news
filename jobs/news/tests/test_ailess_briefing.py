import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ailess_briefing.py"
SPEC = importlib.util.spec_from_file_location("ailess_briefing", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AILessBriefingTest(unittest.TestCase):
    def setUp(self):
        fixture = Path(__file__).parent / "fixtures" / "articles.json"
        self.payload = json.loads(fixture.read_text(encoding="utf-8"))

    def test_selection_is_deterministic_and_deduplicated(self):
        first, first_report = MODULE.select_articles(self.payload, "it")
        second, second_report = MODULE.select_articles(self.payload, "it")
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)
        self.assertEqual(first_report["model_route"], "none")
        self.assertEqual(first_report["rejected"]["duplicate"], 1)
        self.assertEqual(first_report["rejected"]["missing_required_field"], 1)
        self.assertEqual(first_report["rejected"]["source_quota"], 1)
        self.assertEqual(len(first), 5)
        self.assertEqual(first_report["selected_source_count"], 2)

    def test_tracking_and_html_are_removed(self):
        selected, _ = MODULE.select_articles(self.payload, "morning")
        policy = next(item for item in selected if item.source == "국내통신")
        self.assertEqual(policy.url, "https://example.com/policy")
        self.assertEqual(policy.summary, "정책의 주요 내용을 발표했다.")

    def test_feed_metadata_is_removed_and_summary_is_short(self):
        raw = (
            "submitted by /u/test [link] Article URL: https://example.com "
            "Comments URL: https://news.example/item Points: 12 # Comments: 3"
        )
        self.assertEqual(MODULE.clean_summary(raw), "")
        long_summary = "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다."
        self.assertEqual(
            MODULE.clean_summary(long_summary),
            "첫 번째 문장입니다. 두 번째 문장입니다.",
        )

    def test_it_political_noise_is_rejected(self):
        payload = {
            "articles": [
                {
                    "source": "전자신문",
                    "category": "국내",
                    "title": "트럼프·네타냐후 정상회담, 종전 협상 논의",
                    "url": "https://example.com/politics",
                    "summary": "정치 기사",
                },
                {
                    "source": "전자신문",
                    "category": "국내",
                    "title": "AI 반도체 신제품 공개",
                    "url": "https://example.com/chip",
                    "summary": "기술 기사",
                },
            ]
        }
        selected, report = MODULE.select_articles(payload, "it")
        self.assertEqual([article.title for article in selected], ["AI 반도체 신제품 공개"])
        self.assertEqual(report["rejected"]["category_offtopic"], 1)

    def test_english_title_is_marked(self):
        selected, _ = MODULE.select_articles(self.payload, "it")
        markdown = MODULE.render_markdown(selected, "it", "2026-07-29")
        self.assertIn("· Tech Wire · 영문", markdown)

    def test_shadow_run_writes_no_publish_artifacts(self):
        fixture = Path(__file__).parent / "fixtures" / "articles.json"
        with tempfile.TemporaryDirectory() as directory:
            report = MODULE.run("trend", fixture, Path(directory), "2026-07-29")
            markdown = (Path(directory) / "trend-briefing.md").read_text()
            saved_report = json.loads(
                (Path(directory) / "trend-report.json").read_text()
            )
            self.assertIn("# 2026-07-29 트렌드", markdown)
            self.assertEqual(report["publication"], "disabled")
            self.assertEqual(saved_report["model_route"], "none")


if __name__ == "__main__":
    unittest.main()
