import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("collect_candidates.py")
SPEC = importlib.util.spec_from_file_location("collect_candidates", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.sessions = self.root / "agents" / "main" / "sessions"
        self.sessions.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write_session(self, session_id, updated_ms, records, suffix=".jsonl"):
        path = self.sessions / f"{session_id}{suffix}"
        path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in records) + "\n", encoding="utf-8")
        return path, {"sessionId": session_id, "updatedAt": updated_ms, "sessionFile": str(path)}

    def test_emits_bounded_metadata_without_message_bodies(self):
        records = [
            {"type": "session", "timestamp": "2026-08-24T00:00:00Z"},
            {"type": "message", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "name": "read", "arguments": {"path": "/x/skills/orchestration/SKILL.md"}},
                {"type": "toolResult", "name": "read", "text": "Error: missing launcher"},
            ]}},
            {"type": "message", "message": {"role": "user", "content": "그건 잘못된 판단이고 PRIVATE_BODY는 출력하면 안 돼"}},
        ]
        path, entry = self.write_session("abc", 1787529600000, records)
        (self.sessions / "sessions.json").write_text(json.dumps({"route": entry}), encoding="utf-8")
        result = MODULE.collect(self.root, datetime(2026, 8, 24, tzinfo=timezone.utc), 7, 5, 3)
        rendered = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("PRIVATE_BODY", rendered)
        self.assertEqual(result["candidates"][0]["skill"], "orchestration")
        self.assertEqual(result["candidates"][0]["corrections"], 1)
        self.assertEqual(result["candidates"][0]["tool_errors"], 1)
        self.assertEqual(result["candidates"][0]["session_refs"][0]["path"], str(path.resolve()))

    def test_excludes_trajectory_and_caps_candidates_and_refs(self):
        index = {}
        for number, skill in enumerate(("alpha", "beta", "gamma")):
            for copy in range(2):
                session_id = f"{skill}-{copy}"
                records = [
                    {"type": "session", "timestamp": "2026-08-24T00:00:00Z"},
                    {"type": "message", "message": {"role": "assistant", "content": [
                        {"type": "toolCall", "name": "read", "arguments": {"path": f"/x/skills/{skill}/SKILL.md"}}
                    ]}},
                ]
                _, index[session_id] = self.write_session(session_id, 1787529600000 + number, records)
        _, index["trajectory"] = self.write_session(
            "trajectory", 1787529600000,
            [{"type": "session"}, {"type": "message", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "arguments": {"path": "/x/skills/hidden/SKILL.md"}}
            ]}}], suffix=".trajectory.jsonl")
        (self.sessions / "sessions.json").write_text(json.dumps(index), encoding="utf-8")
        result = MODULE.collect(self.root, datetime(2026, 8, 24, tzinfo=timezone.utc), 7, 2, 1)
        self.assertEqual(len(result["candidates"]), 2)
        self.assertTrue(all(len(row["session_refs"]) == 1 for row in result["candidates"]))
        self.assertNotIn("hidden", {row["skill"] for row in result["candidates"]})

    def test_quoted_old_correction_is_not_counted_as_current(self):
        quoted = "잘못된 판단" + (" 과거 대화" * 400) + "\nCurrent user request:\n지금 상태만 확인해줘"
        records = [
            {"type": "session", "timestamp": "2026-08-24T00:00:00Z"},
            {"type": "message", "message": {"role": "assistant", "content": [
                {"type": "toolCall", "name": "read", "arguments": {"path": "/x/skills/orchestration/SKILL.md"}}
            ]}},
            {"type": "message", "message": {"role": "user", "content": quoted}},
        ]
        _, entry = self.write_session("quoted", 1787529600000, records)
        (self.sessions / "sessions.json").write_text(json.dumps({"route": entry}), encoding="utf-8")
        result = MODULE.collect(self.root, datetime(2026, 8, 24, tzinfo=timezone.utc), 7, 5, 3)
        self.assertEqual(result["candidates"][0]["corrections"], 0)


if __name__ == "__main__":
    unittest.main()
