import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "bridge.py"
SPEC = importlib.util.spec_from_file_location("orca_openclaw_bridge", MODULE_PATH)
assert SPEC and SPEC.loader
bridge = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bridge
SPEC.loader.exec_module(bridge)


def make_config(root: Path, allowed_types=("worker_done",)):
    return bridge.BridgeConfig(
        source=bridge.SourceConfig(
            ssh_target="user@company",
            wsl_distro="Ubuntu",
            orca_command="/usr/local/bin/orca-ide",
            observer_terminal="term_observer",
            wait_timeout_ms=1000,
        ),
        openclaw=bridge.OpenClawConfig(
            command="/opt/homebrew/bin/openclaw",
            agent="main",
            session_key="agent:main:test",
        ),
        state_path=root / "state.json",
        allowed_types=allowed_types,
    )


def delivery(event_type="worker_done", body="done"):
    return {
        "ok": True,
        "result": {
            "deliveryId": "delivery_1",
            "messages": [
                {
                    "id": "msg_1",
                    "run_id": "run_observer",
                    "type": event_type,
                    "priority": "normal",
                    "subject": "finished",
                    "body": body,
                    "thread_id": "thread_1",
                    "created_at": "2026-08-14T00:00:00Z",
                    "payload": {
                        "taskId": "task_1",
                        "dispatchId": "ctx_1",
                        "outcome": "succeeded",
                        "ignoredSecret": "must-not-pass",
                    },
                }
            ],
            "count": 1,
            "timedOut": False,
        },
    }


class BridgeTests(unittest.TestCase):
    def test_builds_wait_command_without_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            command = bridge.build_wait_command(config)
        self.assertEqual(command[0], "ssh")
        self.assertIn("--wait", command)
        self.assertEqual(command[-1], "--json")
        self.assertNotIn("sh", command[:1])

    def test_sanitizes_secrets_and_projects_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            response = delivery(body="password=hunter2 Authorization: Bearer abc123")
            message = response["result"]["messages"][0]
            envelope = bridge.build_openclaw_envelope(
                message, "delivery_1", config
            )
        self.assertNotIn("hunter2", envelope)
        self.assertNotIn("abc123", envelope)
        self.assertNotIn("ignoredSecret", envelope)
        self.assertIn("[REDACTED]", envelope)
        self.assertIn("task_1", envelope)

    def test_status_copy_preserves_effective_lifecycle_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp), allowed_types=("question",))
            response = delivery(event_type="status")
            message = response["result"]["messages"][0]
            message["payload"].update(
                {
                    "bridgeEventType": "question",
                    "sourceMessageId": "msg_original_question",
                }
            )
            envelope = bridge.build_openclaw_envelope(
                message, "delivery_1", config
            )
        self.assertIn('"type":"question"', envelope)
        self.assertIn('"transport_type":"status"', envelope)
        self.assertIn("msg_original_question", envelope)

    def test_string_encoded_payload_is_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp), allowed_types=("question",))
            response = delivery(event_type="status")
            message = response["result"]["messages"][0]
            message["payload"] = json.dumps(
                {
                    "bridgeEventType": "question",
                    "sourceRunId": "run_source",
                    "sourceMessageId": "msg_source",
                }
            )
            envelope = bridge.build_openclaw_envelope(
                message, "delivery_1", config
            )
            correlation = bridge.event_correlation(message)

        self.assertIn('"type":"question"', envelope)
        self.assertEqual(correlation["sourceRunId"], "run_source")

    def test_response_uses_stdin_and_never_embeds_user_text_in_ssh_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp), allowed_types=("question",))
            state = bridge.StateStore(config.state_path)
            state.mark_event(
                "msg_bridge",
                "delivered",
                "question",
                {
                    "sourceRunId": "run_source",
                    "sourceMessageId": "msg_source",
                    "questionId": "question_1",
                },
            )
            captured = {}

            def fake_run(command, stdin_text=None):
                captured["command"] = list(command)
                captured["stdin"] = stdin_text
                return {"ok": True, "result": {"messageId": "msg_response"}}

            with mock.patch.object(bridge, "run_json_command", fake_run):
                bridge.respond_to_event(
                    "msg_bridge", "승인; $(touch /tmp/never)", config, state
                )

        command_text = " ".join(captured["command"])
        self.assertNotIn("touch", command_text)
        self.assertNotIn("승인", command_text)
        request = json.loads(captured["stdin"])
        self.assertEqual(request["body"], "승인; $(touch /tmp/never)")
        self.assertEqual(request["source_run_id"], "run_source")
        self.assertEqual(
            state.event_entry("msg_bridge")["response_status"], "sent"
        )

    def test_response_requires_source_run_correlation(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)
            state.mark_event("msg_bridge", "delivered", "question")
            with self.assertRaises(bridge.BridgeError):
                bridge.respond_to_event("msg_bridge", "yes", config, state)

    def test_pending_responses_lists_only_unanswered_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = bridge.StateStore(Path(tmp) / "state.json")
            state.mark_event(
                "msg_question",
                "delivered",
                "question",
                {"sourceRunId": "run_source"},
            )
            state.mark_event("msg_status", "delivered", "status")
            state.mark_event(
                "msg_answered",
                "delivered",
                "decision_gate",
                {"sourceRunId": "run_source"},
            )
            state.mark_response("msg_answered", "sent")

            pending = state.pending_responses()

        self.assertEqual([item["event_id"] for item in pending], ["msg_question"])

    def test_delivers_then_acks(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)
            commands = []

            def runner(command):
                commands.append(list(command))
                if command[1] == "agent":
                    return {"status": "ok"}
                return {
                    "ok": True,
                    "result": {"acknowledged": "delivery_1"},
                }

            result = bridge.process_delivery(delivery(), config, state, runner)
            self.assertEqual(result, "delivery_1")
            self.assertEqual(state.event_status("msg_1"), "delivered")
            self.assertEqual(
                state.data["deliveries"]["delivery_1"]["status"], "acked"
            )
            self.assertEqual(len(commands), 2)
            self.assertEqual(commands[0][1], "agent")
            self.assertIn("--ack", commands[1])

    def test_openclaw_failure_is_not_acked_and_becomes_ambiguous(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)
            commands = []

            def runner(command):
                commands.append(list(command))
                raise bridge.BridgeError("gateway unavailable")

            with self.assertRaises(bridge.BridgeError):
                bridge.process_delivery(delivery(), config, state, runner)
            self.assertEqual(state.event_status("msg_1"), "unknown")
            self.assertEqual(len(commands), 1)
            with self.assertRaises(bridge.BridgeError):
                bridge.process_delivery(delivery(), config, state, runner)

    def test_duplicate_delivered_event_only_retries_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)
            state.mark_event("msg_1", "delivered", "worker_done")
            commands = []

            def runner(command):
                commands.append(list(command))
                return {
                    "ok": True,
                    "result": {"acknowledged": "delivery_1"},
                }

            bridge.process_delivery(delivery(), config, state, runner)
            self.assertEqual(len(commands), 1)
            self.assertIn("--ack", commands[0])

    def test_non_allowlisted_message_is_skipped_but_batch_is_acked(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)
            commands = []

            def runner(command):
                commands.append(list(command))
                return {
                    "ok": True,
                    "result": {"acknowledged": "delivery_1"},
                }

            bridge.process_delivery(delivery(event_type="heartbeat"), config, state, runner)
            self.assertEqual(state.event_status("msg_1"), "skipped")
            self.assertEqual(len(commands), 1)
            self.assertIn("--ack", commands[0])

    def test_dry_run_never_calls_runner_or_writes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = make_config(Path(tmp))
            state = bridge.StateStore(config.state_path)

            def runner(_command):
                raise AssertionError("runner should not be called")

            result = bridge.process_delivery(
                delivery(), config, state, runner, dry_run=True
            )
            self.assertEqual(result, "delivery_1")
            self.assertIsNone(state.event_status("msg_1"))
            self.assertFalse(config.state_path.exists())

    def test_config_rejects_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "source": {
                            "ssh_target": "REPLACE_ME@host",
                            "wsl_distro": "Ubuntu",
                            "orca_command": "/orca",
                            "observer_terminal": "term_1",
                        },
                        "openclaw": {
                            "command": "openclaw",
                            "agent": "main",
                            "session_key": "agent:main:test",
                        },
                        "state_path": str(Path(tmp) / "state.json"),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(bridge.BridgeError):
                bridge.load_config(path)


if __name__ == "__main__":
    unittest.main()
