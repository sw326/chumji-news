import json
import tempfile
import unittest
from pathlib import Path

from refresh_current_market import refresh, validate_candidate


def candidate(china_status="not-manually-verified"):
    partners = [
        {"country_code": code, "data_status": "available"}
        for code in ("US", "HU", "PL")
    ] + [{"country_code": "CN", "data_status": china_status}]
    return {
        "as_of": "2026-08-06",
        "latest_periods": {"korea_customs": "2026-07", "US": "2026-07", "HU": "2026-06", "PL": "2026-06", "CN": "2026-07"},
        "korea": {"rows": [{}], "classification_precision": {"total_value_usd": 100, "broad_value_usd": 10}},
        "partner_statistics": partners,
        "review_gate": {
            "automated_sources_complete": True,
            "blockers": [],
            "china_manual_check": {"status": "pending-one-time-verification", "target_period": "2026-07"},
        },
    }


class RefreshCurrentMarketTest(unittest.TestCase):
    def test_pending_china_does_not_block_automated_refresh(self):
        validate_candidate(candidate())

    def test_failed_candidate_preserves_published_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output, html = root / "board.json", root / "board.html"
            state, lock = root / "state.json", root / "refresh.lock"
            output.write_text('{"old": true}', encoding="utf-8")
            html.write_text("old html", encoding="utf-8")

            def broken(_key):
                board = candidate()
                board["review_gate"]["blockers"] = ["bad data"]
                return board

            with self.assertRaises(RuntimeError):
                refresh("key", output=output, html_output=html, state_output=state, lock_file=lock, builder=broken)
            self.assertEqual('{"old": true}', output.read_text(encoding="utf-8"))
            self.assertEqual("old html", html.read_text(encoding="utf-8"))
            self.assertEqual("failed-preserved-last-good", json.loads(state.read_text())["status"])


if __name__ == "__main__":
    unittest.main()
