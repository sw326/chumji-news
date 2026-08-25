import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "run_shadow.py"
SPEC = importlib.util.spec_from_file_location("fresh_food_run_shadow", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FreshFoodShadowTest(unittest.TestCase):
    def test_default_template_uses_surviving_web_root(self):
        expected = MODULE_PATH.parents[3] / "public/fresh-food/index.html"
        self.assertEqual(MODULE.default_template_path(), expected)

    def test_validation_records_missing_items(self):
        report = {
            "items": [
                {"label": "배추 고랭지 상품 / 소매"},
                {"label": "양파 양파 상품 / 소매"},
            ],
            "errors": [{"item": "무", "error": "seasonal"}],
        }
        validation = MODULE.validate_report(report)
        self.assertEqual(validation["covered_items"], ["배추", "양파"])
        self.assertEqual(validation["missing_items"], ["대파", "무"])
        self.assertEqual(validation["error_count"], 1)

    def test_validation_accepts_all_items(self):
        report = {
            "items": [{"label": f"{name} 상품 / 소매"} for name in MODULE.ITEMS],
            "errors": [],
        }
        validation = MODULE.validate_report(report)
        self.assertEqual(validation["item_count"], 4)
        self.assertEqual(validation["missing_items"], [])

    def test_collector_uses_https_endpoints(self):
        collector_path = MODULE_PATH.with_name("fresh_price_alert.py")
        source = collector_path.read_text(encoding="utf-8")
        self.assertNotIn('"http://apis.data.go.kr/', source)
        self.assertIn('"https://apis.data.go.kr/', source)
        self.assertIn("REQUEST_ATTEMPTS", source)

    def test_view_fetches_recent_catalog_once(self):
        generator_path = MODULE_PATH.with_name("generate_price_view.py")
        source = generator_path.read_text(encoding="utf-8")
        main_source = source[source.index("def main()") :]
        self.assertEqual(main_source.count('request_json(ENDPOINTS["recent"]'), 1)

    def test_shadow_status_records_collector_exit(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('"collector_exit_code": result.returncode', source)


if __name__ == "__main__":
    unittest.main()
