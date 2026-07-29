import importlib.util
import sys
import unittest
from pathlib import Path

JOB_DIR = Path(__file__).parents[1]
sys.path.insert(0, str(JOB_DIR))
SPEC = importlib.util.spec_from_file_location("global_intel_run_shadow", JOB_DIR / "run_shadow.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GlobalIntelShadowTest(unittest.TestCase):
    def test_error_categories_are_redacted(self):
        self.assertEqual(MODULE.error_category("HTTP Error 403: Forbidden"), "http_403")
        self.assertEqual(MODULE.error_category("SSL handshake timed out"), "timeout")

    def test_source_health_supports_partial_results(self):
        payload = {
            "acled": {"error": "HTTP Error 403"},
            "gdelt": {"regions": {
                "A": {"article_count": 2},
                "B": {"error": "timeout"},
            }},
            "opensky": {"zones": {
                "A": {"total_aircraft": 10},
                "B": {"total_aircraft": 5},
            }},
        }
        health = MODULE.source_health(payload)
        self.assertEqual(health["acled"]["error"], "http_403")
        self.assertEqual(health["gdelt"]["status"], "partial")
        self.assertEqual(health["opensky"]["status"], "ok")

    def test_report_includes_interpretation_warning(self):
        payload = {
            "acled": {"error": "403"},
            "gdelt": {"regions": {}},
            "opensky": {"zones": {
                "Korean Peninsula": {
                    "total_aircraft": 10,
                    "no_callsign_count": 2,
                }
            }},
        }
        markdown = MODULE.render_markdown(
            payload, MODULE.source_health(payload), "2026-07-29"
        )
        self.assertIn("군사 활동의 증거가 아닙니다", markdown)
        self.assertIn("단일 시점 수치만으로", markdown)


if __name__ == "__main__":
    unittest.main()
