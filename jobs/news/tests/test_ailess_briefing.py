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
