import json
import subprocess
import sys
import unittest

from operations.producers.news import task_control
from operations.producers.news.tests import test_task_control as fixtures


class ScheduledTrendTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.TaskControlTests("test_start_paused_and_completed_no_replay")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.env["CHUMJI_NEWS_CHECKPOINT_ROOT"] = str(self.fixture.root / "checkpoints")
        self.fixture.run = self.fixture.root / "checkpoints/trend" / task_control.today()

    def invoke(self):
        return subprocess.run([sys.executable, str(self.fixture.news / "scheduled_trend.py")],
                              env=self.fixture.env, capture_output=True, text=True, timeout=20)

    def test_duplicate_scheduler_invocation_does_not_repeat_pipeline(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(second.stdout)["action"], "not_restarted")
        self.assertEqual(self.fixture.events(), ["collect", "summarize", "publish"])

    def test_paused_run_is_not_automatically_resumed(self):
        self.assertEqual(self.fixture.invoke("start", "--publish", "--start-paused").returncode, 0)
        result = self.invoke()
        self.assertEqual(result.returncode, 75, result.stderr)
        self.assertEqual(self.fixture.events(), [])

    def test_failed_publication_is_not_retried(self):
        (self.fixture.root / "fail-publish").touch()
        self.assertNotEqual(self.invoke().returncode, 0)
        (self.fixture.root / "fail-publish").unlink()
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.fixture.events(), ["collect", "summarize", "publish"])

    def test_incomplete_directory_is_not_recreated(self):
        self.fixture.run.mkdir(parents=True)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.fixture.events(), [])

    def test_session_bookkeeping_does_not_block_resume(self):
        self.assertEqual(self.fixture.invoke("start", "--start-paused",
                                            env=self.fixture.env | {"OPENCLAW_SESSION_ID": "cron-test"}).returncode, 0)
        result = self.fixture.invoke("resume", env=self.fixture.env | {"OPENCLAW_SESSION_ID": "owner-resume"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.fixture.events(), ["collect", "summarize"])


class ScheduledMorningTests(ScheduledTrendTests):
    profile = "morning"

    def setUp(self):
        super().setUp()
        self.fixture.profile = self.profile
        self.fixture.run = self.fixture.root / "checkpoints" / self.profile / task_control.today()

    def invoke(self):
        return subprocess.run([sys.executable, str(self.fixture.news / "scheduled_profile.py"), self.profile],
                              env=self.fixture.env, capture_output=True, text=True, timeout=20)


class ScheduledITTests(ScheduledMorningTests):
    profile = "it"


if __name__ == "__main__":
    unittest.main()
