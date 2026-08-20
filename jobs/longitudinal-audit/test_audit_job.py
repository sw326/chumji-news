import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("audit_job.py")
SPEC = importlib.util.spec_from_file_location("audit_job", MODULE_PATH)
audit_job = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules["audit_job"] = audit_job
SPEC.loader.exec_module(audit_job)


def write_transcript(path: Path, messages: list[dict]) -> None:
    rows = [{"type": "session", "id": "session-a", "timestamp": "2026-08-20T00:00:00Z"}, *messages]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


class AuditJobTests(unittest.TestCase):
    def test_collects_only_completed_owner_telegram_turns(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "main" / "sessions"
            directory.mkdir(parents=True)
            write_transcript(directory / "11111111-1111-1111-1111-111111111111.jsonl", [
                {"type": "message", "id": "a", "timestamp": "2026-08-20T00:01:00Z", "message": {"role": "user", "sourceChannel": "telegram", "senderId": audit_job.OWNER_ID, "content": "완료 턴"}},
                {"type": "message", "id": "b", "timestamp": "2026-08-20T00:02:00Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "응답"}]}},
                {"type": "message", "id": "c", "timestamp": "2026-08-20T00:03:00Z", "message": {"role": "user", "sourceChannel": "telegram", "senderId": audit_job.OWNER_ID, "content": "진행 중"}},
            ])
            turns, errors = audit_job.collect(Path(raw), ("", ""))
            self.assertEqual(errors, [])
            self.assertEqual([turn.user_text for turn in turns], ["완료 턴"])

    def test_deduplicates_reset_archive(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "wiki-lab" / "sessions"
            directory.mkdir(parents=True)
            messages = [
                {"type": "message", "id": "same", "timestamp": "2026-08-20T00:01:00Z", "message": {"role": "user", "sourceChannel": "telegram", "senderId": audit_job.OWNER_ID, "content": "중복"}},
                {"type": "message", "id": "answer", "timestamp": "2026-08-20T00:02:00Z", "message": {"role": "assistant", "content": "응답"}},
            ]
            write_transcript(directory / "22222222-2222-2222-2222-222222222222.jsonl", messages)
            write_transcript(directory / "22222222-2222-2222-2222-222222222222.jsonl.reset.2026-08-20T00-03-00Z", messages)
            turns, errors = audit_job.collect(Path(raw), ("", ""))
            self.assertEqual(errors, [])
            self.assertEqual(len(turns), 1)

    def test_batch_requires_direct_input_size(self):
        turn = audit_job.Turn(("t", "k"), "main", "s", "f", "m", "t", "telegram", "", "12345")
        self.assertEqual(audit_job.make_batch([turn], 6, 10), [])
        self.assertEqual(len(audit_job.make_batch([turn, turn], 6, 10)), 2)

    def test_ignores_only_incomplete_trailing_active_record(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "main" / "sessions"
            directory.mkdir(parents=True)
            path = directory / "33333333-3333-3333-3333-333333333333.jsonl"
            write_transcript(path, [
                {"type": "message", "id": "a", "timestamp": "2026-08-20T00:01:00Z", "message": {"role": "user", "sourceChannel": "telegram", "senderId": audit_job.OWNER_ID, "content": "완료 턴"}},
                {"type": "message", "id": "b", "timestamp": "2026-08-20T00:02:00Z", "message": {"role": "assistant", "content": "응답"}},
            ])
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"type":"message"')
            turns, errors = audit_job.collect(Path(raw), ("", ""))
            self.assertEqual(errors, [])
            self.assertEqual([turn.user_text for turn in turns], ["완료 턴"])


if __name__ == "__main__":
    unittest.main()
