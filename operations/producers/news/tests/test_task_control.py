"""Real controller + shell, fake collectors/model/publisher; no external calls."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from operations.producers.news.tests.test_collection_health import payload_for
from operations.producers.news import task_control

ROOT = Path(__file__).parents[1]


class TaskControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.news = self.root / "news"
        shutil.copytree(ROOT, self.news, ignore=shutil.ignore_patterns("__pycache__"))
        self.run = self.root / "run"
        self.profile = "trend"
        self.env = os.environ | {"CHUMJI_NEWS_LOG_DIR": str(self.root / "logs"),
                                 "CHUMJI_NEWS_RECEIPT_DIR": str(self.root / "receipts"),
                                 "CHUMJI_NEWS_SUPABASE_ENV": str(self.root / "dummy.env"),
                                 "CHUMJI_NEWS_TELEGRAM_TOKEN_FILE": str(self.root / "dummy-token")}
        (self.root / "dummy.env").write_text("NEXT_PUBLIC_SUPABASE_URL=https://example.test\nSUPABASE_SERVICE_ROLE_KEY=fixture-only\n")
        (self.root / "dummy-token").write_text("fixture-only")
        self.fake("fetch_trends.py", "collect", json.dumps(payload_for("ok")))
        self.fake("fetch_morning_news.py", "collect", json.dumps(payload_for("ok")))
        self.fake("fetch_it_tech.py", "collect", json.dumps(payload_for("ok")))
        self.fake("adapters/openclaw_gpt_summarize.sh", "summarize", "Title\n" + "Source-backed summary. " * 60)
        self.fake("adapters/publish.py", "publish", "published")

    def fake(self, path, stage, output):
        target = self.news / path
        target.write_text(
            "#!/usr/bin/env python3\nimport sys,time\nfrom pathlib import Path\n"
            f"root=Path({str(self.root)!r})\nstage={stage!r}\n"
            "with (root/'events').open('a') as f: f.write(stage+'\\n')\n"
            "(root/(stage+'-entered')).touch()\n"
            "deadline=time.monotonic()+12\n"
            "while (root/('block-'+stage)).exists():\n"
            " if time.monotonic()>deadline: sys.exit(8)\n"
            " time.sleep(.01)\n"
            "if (root/('fail-'+stage)).exists(): sys.exit(1)\n"
            f"print({output!r})\n")
        target.chmod(0o755)

    def command(self, action, *extra):
        prefix = [sys.executable, str(self.news / "task_control.py"), action]
        return prefix + ([self.profile, "--directory", str(self.run)] if action == "start" else [str(self.run)]) + list(extra)

    def invoke(self, action, *extra, env=None):
        return subprocess.run(self.command(action, *extra), env=env or self.env,
                              text=True, capture_output=True, timeout=15)

    def launch(self, action="start", *extra):
        proc = subprocess.Popen(self.command(action, *extra), env=self.env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            for gate in self.root.glob("block-*"):
                gate.unlink(missing_ok=True)
            if proc.poll() is None:
                proc.terminate()
            proc.communicate(timeout=15)
        self.addCleanup(cleanup)
        return proc

    def await_stage(self, stage):
        deadline = time.monotonic() + 8
        while not (self.root / (stage + "-entered")).exists():
            if time.monotonic() > deadline:
                self.fail("stage was not reached: " + stage)
            time.sleep(.01)

    def events(self):
        p = self.root / "events"
        return p.read_text().splitlines() if p.exists() else []

    def state(self):
        return json.loads((self.run / "state.json").read_text())

    def pause_during(self, stage, publish=False):
        gate = self.root / ("block-" + stage)
        gate.touch()
        proc = self.launch("start", *(["--publish"] if publish else []))
        self.await_stage(stage)
        request = self.invoke("pause")
        self.assertEqual(request.returncode, 0, request.stderr)
        self.assertTrue(json.loads(request.stdout)["local_worker_active"])
        self.assertEqual(json.loads(request.stdout)["active_stage"], stage)
        gate.unlink()
        out, err = proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 75, out + err)
        self.assertEqual(self.state()["status"], "paused")

    def test_start_paused_and_completed_no_replay(self):
        self.assertEqual(self.invoke("start", "--start-paused").returncode, 0)
        self.assertEqual(self.events(), [])
        result = self.invoke("resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events(), ["collect", "summarize"])
        self.assertEqual(self.state()["status"], "completed")
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertEqual(self.events(), ["collect", "summarize"])

    def test_morning_and_it_support_controlled_dry_run(self):
        for profile in ("morning", "it"):
            with self.subTest(profile=profile):
                self.profile = profile
                self.run = self.root / ("run-" + profile)
                result = self.invoke("start")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.state()["status"], "completed")
                self.assertNotIn("publish", self.events())
    def test_pause_after_collection_reuses_source(self):
        self.pause_during("collect")
        self.assertEqual(self.events(), ["collect"])
        result = self.invoke("resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events(), ["collect", "summarize"])

    def test_pause_after_summary_then_publish_without_recompute_or_secret_retention(self):
        self.pause_during("summarize", publish=True)
        self.assertEqual(self.events(), ["collect", "summarize"])
        result = self.invoke("resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events(), ["collect", "summarize", "publish"])
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertFalse((self.run / "artifacts/supabase.key").exists())
        for path in self.run.rglob("*"):
            if path.is_file():
                self.assertNotIn("fixture-only", path.read_text())

    def test_pause_during_publication_does_not_claim_to_undo_send(self):
        gate = self.root / "block-publish"
        gate.touch()
        proc = self.launch("start", "--publish")
        self.await_stage("publish")
        view = json.loads(self.invoke("pause").stdout)
        self.assertEqual(view["status"], "running")
        self.assertEqual(view["active_stage"], "publish")
        gate.unlink()
        proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.state()["status"], "completed")

    def test_concurrent_resume_is_rejected(self):
        (self.root / "block-collect").touch()
        proc = self.launch()
        self.await_stage("collect")
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        (self.root / "block-collect").unlink()
        proc.communicate(timeout=15)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(self.events(), ["collect", "summarize"])

    def test_killed_controller_does_not_unlock_live_pipeline(self):
        (self.root / "block-collect").touch()
        proc = self.launch()
        self.await_stage("collect")
        proc.kill()
        proc.wait(timeout=5)
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertTrue(json.loads(self.invoke("status").stdout)["local_worker_active"])
        self.invoke("pause")
        (self.root / "block-collect").unlink()
        proc.communicate(timeout=15)  # pipes close when inherited shell finishes
        self.assertEqual(self.state()["status"], "paused")
        self.assertEqual(self.invoke("resume").returncode, 0)
        self.assertEqual(self.events(), ["collect", "summarize"])

    def test_modified_artifact_blocks_resume(self):
        self.pause_during("collect")
        (self.run / "artifacts/source.json").write_text("{}")
        result = self.invoke("resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact changed", result.stderr)
        self.assertEqual(self.events(), ["collect"])

    def test_changed_code_and_environment_block_resume(self):
        self.assertEqual(self.invoke("start", "--start-paused").returncode, 0)
        self.assertNotEqual(self.invoke("resume", env=self.env | {"OPENCLAW_MODEL": "changed"}).returncode, 0)
        with (self.news / "fetch_trends.py").open("a") as output:
            output.write("\n# changed code\n")
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertEqual(self.events(), [])

    def test_unknown_publication_is_not_retried(self):
        (self.root / "fail-publish").touch()
        self.assertNotEqual(self.invoke("start", "--publish").returncode, 0)
        self.assertEqual(self.state()["status"], "needs_attention")
        self.assertEqual(self.state()["active_stage"], "publish")
        (self.root / "fail-publish").unlink()
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertEqual(self.events(), ["collect", "summarize", "publish"])

    def test_replaced_publication_config_blocks_resume(self):
        result = self.invoke("start", "--publish", "--start-paused")
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "dummy.env").write_text("NEXT_PUBLIC_SUPABASE_URL=https://changed.test\nSUPABASE_SERVICE_ROLE_KEY=fixture-only\n")
        result = self.invoke("resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("environment changed", result.stderr)
        self.assertEqual(self.events(), [])

    def test_changed_prompt_blocks_resume(self):
        self.assertEqual(self.invoke("start", "--start-paused").returncode, 0)
        prompt = next((self.news / "prompts").glob("*.md"))
        prompt.write_text(prompt.read_text() + "\nChanged instructions\n")
        result = self.invoke("resume")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("code or environment changed", result.stderr)
        self.assertEqual(self.events(), [])

    def test_failed_model_is_not_blindly_restarted(self):
        (self.root / "fail-summarize").touch()
        self.assertNotEqual(self.invoke("start").returncode, 0)
        self.assertEqual(self.state()["status"], "needs_attention")
        self.assertNotEqual(self.invoke("resume").returncode, 0)

    def test_known_read_failure_can_resume(self):
        (self.root / "fail-collect").touch()
        self.assertNotEqual(self.invoke("start").returncode, 0)
        self.assertEqual(self.state()["status"], "failed")
        (self.root / "fail-collect").unlink()
        result = self.invoke("resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.events(), ["collect", "collect", "summarize"])

    def test_stale_publication_checkpoint_is_blocked(self):
        self.invoke("start", "--publish", "--start-paused")
        state = self.state()
        state["date"] = "2000-01-01"
        (self.run / "state.json").write_text(json.dumps(state))
        self.assertNotEqual(self.invoke("resume").returncode, 0)
        self.assertEqual(self.events(), [])

    def test_date_rollover_before_publish_is_blocked_at_stage_boundary(self):
        self.pause_during("summarize", publish=True)
        state = self.state()
        state.update(status="running", pause_requested=False)
        (self.run / "state.json").write_text(json.dumps(state))
        with (patch.object(task_control, "ROOT", self.news.resolve()),
              patch.object(task_control, "fingerprint", return_value=(state["code_hash"], state["settings_hash"])),
              patch.object(task_control, "today", return_value="2099-01-01")):
            with self.assertRaisesRegex(ValueError, "another KST date"):
                task_control.internal(self.run, "enter", "publish", [])
        self.assertIsNone(self.state()["active_stage"])
        self.assertEqual(self.events(), ["collect", "summarize"])


if __name__ == "__main__":
    unittest.main()
