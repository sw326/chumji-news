"""Offline transport and whole-run continuation recovery regressions."""
import copy
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch

import actions as a
import resume as r
import sequential as s


class ResumeRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name) / "source"
        self.dest = Path(self.tmp.name) / "continuation"
        self.runner = a.claims.runner
        patches = [
            patch.object(a, "MAX_CALLS", s.MAX_CALLS),
            patch.dict(a.RULES, {"news": s.NEWS_RULE}),
            patch.object(self.runner, "CRITERIA", copy.deepcopy(a.SEARCH)),
            patch.object(s.sys, "version_info", (3, 11, 0)),
            patch.object(s.time, "sleep"),
            patch.dict(os.environ, {"AI_GATEWAY_API_KEY": "offline-test-only"}),
            patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")),
            patch.object(self.runner.urllib.request, "urlopen", side_effect=AssertionError("Network forbidden")),
            patch("builtins.print"),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def response(self, choice="return_candidates"):
        return {
            "answers": {"topic": {
                "type": "choice", "choice": choice,
                "probabilities": {key: float(key == choice) for key in a.SEARCH},
            }},
            "usage": {"inputTokens": 7, "outputTokens": 1, "cost": 0},
        }

    def successful_row(self, task):
        return {
            "id": task["id"], "arm": "jev", "status": "ok",
            "request_sha256": task["sha256"], "topic": "return_candidates",
            "response": self.response(), "latency_ms": 1,
            "input_tokens": 7, "output_tokens": 1,
            "reported_cost_usd": 0, "list_cost_usd": 0,
        }

    @staticmethod
    def failed_row(task):
        return {
            "id": task["id"], "arm": "jev", "status": "error",
            "request_sha256": task["sha256"],
            "error_type": "HTTPError", "http_status": 429,
        }

    @staticmethod
    def write_rows(path, rows):
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def source_with_recorded_responses(self, pending=0):
        """Real frozen files; the first success has not yet reached state.json."""
        self.source.mkdir()
        (self.source / "controller.lock").touch()
        document = {
            "id": "d", "title": "Public reference", "text": "A frozen public excerpt.",
            "url": "https://example.org/reference", "links": [], "index": "primary",
        }
        catalog = {"secondary": {
            "name": "Empty supplement", "description": "No extra documents.",
            "query_contract": "Same query", "coverage_note": "Synthetic test corpus.",
        }}
        news = {
            "id": "N01", "group": "synthetic_empty",
            "incoming": {"id": "n", "title": "No body", "text": "", "url": "https://example.org/n"},
            "events": [], "seed_articles": [], "expected": {"api": "defer"},
            "allowed_apis": ["defer"],
        }
        cases = [{
            "id": f"S{i:02}", "pair_id": f"Q{(i+1)//2:02}",
            "condition": "routed" if i % 2 else "fullscan", "describe_tools": True,
            "query": "What does the reference say?", "initial_ids": ["d"],
            "required_ids": ["d"], "expected_first": "return_candidates",
            "acceptable_first": ["return_candidates"], "expected_terminal": "return_candidates",
        } for i in range(1, 3 + pending)]
        fixture = {
            "privacy": "public_and_synthetic_only", "news": {"cases": [news]},
            "search": {"documents": [document], "cases": cases, "index_descriptions": catalog},
        }
        a.exclusive(self.source / "fixture.json", fixture)
        (self.source / "fixture.sha256").write_text(a.hash_obj(fixture))
        a.exclusive(self.source / "prices.json", {self.runner.MODELS["jev"]: {"input": "0", "output": "0"}})
        a.exclusive(self.source / "rules.json", {"news": s.NEWS_RULE, "search": a.RULES["search"], "max_calls": s.MAX_CALLS})
        (self.source / "news" / "N01").mkdir(parents=True)
        for case in cases:
            p = self.source / "search" / case["id"]
            p.mkdir(parents=True)
            state = s.search_initial(case, fixture)
            a.exclusive(p / "initial.json", state)
            a.exclusive(p / "state.json", state)
        out = a.prepare_batch(self.source, "search", 1)
        tasks = a.read(out / "manifest.json")["tasks"]
        self.write_rows(out / "results.jsonl", [self.successful_row(tasks[0]), self.failed_row(tasks[1])])
        self.before = r.inventory(self.source)
        r.prepare(self.source, self.dest)
        return tasks

    def test_low_level_skips_old_ok_and_error_then_stops_at_new_error(self):
        out = Path(self.tmp.name) / "transport"
        out.mkdir()
        tasks = [{"id": ident, "arm": "jev", "body": {"id": ident},
                  "sha256": a.hash_obj({"id": ident})}
                 for ident in ("old-ok", "old-error", "new-ok", "new-error", "later")]
        manifest = {"interval_seconds": 3.2, "max_calls": len(tasks), "tasks": tasks,
                    "catalog_prices": {self.runner.MODELS["jev"]: {"input": "0", "output": "0"}}}
        raw = self.runner.encoded(manifest)
        (out / "manifest.json").write_bytes(raw)
        (out / "manifest.sha256").write_text(a.claims.digest(raw))
        old = [self.successful_row(tasks[0]), self.failed_row(tasks[1])]
        self.write_rows(out / "results.jsonl", old)
        prefix = (out / "results.jsonl").read_bytes()
        opener = Mock()
        opener.open.side_effect = [io.BytesIO(json.dumps(self.response()).encode()), TimeoutError("offline failure")]
        with patch.object(self.runner.urllib.request, "build_opener", return_value=opener):
            self.runner.execute(out, len(tasks), True)
        sent = [json.loads(call.args[0].data)["id"] for call in opener.open.call_args_list]
        self.assertEqual(sent, ["new-ok", "new-error"])
        self.assertTrue((out / "results.jsonl").read_bytes().startswith(prefix))
        rows = [json.loads(line) for line in (out / "results.jsonl").read_text().splitlines()]
        self.assertEqual(rows[:2], old)
        self.assertEqual([(row["id"], row["status"]) for row in rows[2:]],
                         [("new-ok", "ok"), ("new-error", "error")])
        self.assertEqual(a.read(out / "runs.jsonl")["calls"], 2)

    def test_whole_run_applies_recorded_success_without_resending(self):
        self.source_with_recorded_responses()
        self.assertEqual(a.read(self.dest / "search/S01/state.json")["status"], "active")
        opener = Mock()
        opener.open.side_effect = AssertionError("No request should be resent")
        with patch.object(self.runner.urllib.request, "build_opener", return_value=opener):
            s.run(self.dest, continuation_check=r.verify)
            first = r.inventory(self.dest)
            s.run(self.dest, continuation_check=r.verify)
        opener.open.assert_not_called()
        success = a.read(self.dest / "search/S01/state.json")
        failure = a.read(self.dest / "search/S02/state.json")
        self.assertEqual(success["status"], "returned")
        self.assertEqual(len(success["history"]), 1)
        self.assertEqual(success["packet"][0]["id"], "d")
        self.assertEqual(failure["status"], "handoff")
        self.assertFalse(failure["history"][0]["decision"]["valid"])
        self.assertEqual(r.inventory(self.dest), first)
        self.assertEqual(r.inventory(self.source), self.before)

    def test_new_failure_stops_and_next_run_sends_nothing(self):
        tasks = self.source_with_recorded_responses(pending=2)
        opener = Mock()
        opener.open.side_effect = TimeoutError("new offline failure")
        with patch.object(self.runner.urllib.request, "build_opener", return_value=opener):
            with self.assertRaisesRegex(ValueError, "New or altered failure"):
                s.run(self.dest, continuation_check=r.verify)
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(json.loads(opener.open.call_args.args[0].data), tasks[2]["body"])
            opener.open.reset_mock()
            with self.assertRaisesRegex(ValueError, "New or altered failure"):
                s.run(self.dest, continuation_check=r.verify)
        opener.open.assert_not_called()
        rows = [json.loads(line) for line in (self.dest / "search-round-1/results.jsonl").read_text().splitlines()]
        self.assertEqual([row["id"] for row in rows], ["S01", "S02", "S03"])
        self.assertEqual(a.read(self.dest / "search/S04/state.json")["status"], "active")
        self.assertEqual(r.inventory(self.source), self.before)

    def test_unknown_interrupted_request_blocks_entire_next_run(self):
        self.source_with_recorded_responses(pending=2)
        opener = Mock()
        opener.open.side_effect = KeyboardInterrupt("unknown request outcome")
        with patch.object(self.runner.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(KeyboardInterrupt):
                s.run(self.dest, continuation_check=r.verify)
            self.assertEqual(opener.open.call_count, 1)
            self.assertTrue((self.dest / "search-round-1/inflight.json").exists())
            opener.open.reset_mock()
            with self.assertRaisesRegex(ValueError, "inflight"):
                s.run(self.dest, continuation_check=r.verify)
        opener.open.assert_not_called()
        rows = [json.loads(line) for line in (self.dest / "search-round-1/results.jsonl").read_text().splitlines()]
        self.assertEqual([row["id"] for row in rows], ["S01", "S02"])
        self.assertEqual(r.inventory(self.source), self.before)


if __name__ == "__main__":
    unittest.main()
