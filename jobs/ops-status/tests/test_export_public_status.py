import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

JOB_DIR = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("export_public_status", JOB_DIR / "export_public_status.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExportPublicStatusTest(unittest.TestCase):
    def test_groups_timeline_and_redacts_html(self):
        with tempfile.TemporaryDirectory() as temporary:
            database = Path(temporary) / "history.sqlite3"
            connection = sqlite3.connect(database)
            connection.execute(
                """CREATE TABLE alert_events (
                id INTEGER PRIMARY KEY, source TEXT, event_id TEXT, action TEXT,
                severity TEXT, occurred_at TEXT, received_at TEXT, message_html TEXT)"""
            )
            connection.executemany(
                "INSERT INTO alert_events VALUES(?,?,?,?,?,?,?,?)",
                [
                    (1, "emsc", "event-1", "create", "한국 주변", "2026-07-29T00:00:00Z", "2026-07-29T00:01:00Z", "<b>지진 · 규모 4.4</b>\\n\\nKYUSHU, JAPAN"),
                    (2, "emsc", "event-1", "update", "한국 주변", "2026-07-29T00:00:00Z", "2026-07-29T00:02:00Z", "<b>지진 · 규모 4.7</b>\\n\\nKYUSHU, JAPAN"),
                ],
            )
            connection.commit()
            connection.close()
            alerts = MODULE.alerts_from_db(database)
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["category"], "earthquake")
            self.assertEqual(alerts[0]["status"], "monitoring")
            self.assertEqual(len(alerts[0]["timeline"]), 2)
            self.assertNotIn("<b>", alerts[0]["publicSummary"])

    def test_env_loader_ignores_comments(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "service.env"
            path.write_text("# secret refs\nNEXT_PUBLIC_SUPABASE_URL=https://example.test\n")
            values = MODULE.load_env_file(path)
            self.assertEqual(
                values["NEXT_PUBLIC_SUPABASE_URL"], "https://example.test"
            )
            self.assertNotIn("# secret refs", values)


if __name__ == "__main__":
    unittest.main()
