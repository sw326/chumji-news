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


if __name__ == "__main__":
    unittest.main()
