import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ADAPTER = ROOT / "adapters" / "openclaw_gpt_summarize.sh"

# Stub CLI: fails for models listed in STUB_FAIL_MODELS, otherwise answers with the model name.
STUB = """#!/bin/bash
model=""
while (( $# )); do
  if [[ "$1" == "--model" ]]; then model="$2"; shift; fi
  shift
done
printf '%s\\n' "$model" >>"$STUB_CALLS"
case " $STUB_FAIL_MODELS " in
  *" $model "*) printf 'stub auth failure for %s\\n' "$model" >&2; exit 1 ;;
esac
case " $STUB_EMPTY_MODELS " in
  *" $model "*) printf '{"status":"ok","result":{"payloads":[]}}'; exit 0 ;;
esac
printf '{"status":"ok","result":{"payloads":[{"text":"summary by %s"}]}}' "$model"
"""


@unittest.skipUnless(shutil.which("jq"), "jq is required")
class SummarizeAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.stub = self.tmp / "openclaw"
        self.stub.write_text(STUB)
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IXUSR)
        self.prompt = self.tmp / "prompt.txt"
        self.prompt.write_text("prompt")
        self.log = self.tmp / "adapter.log"
        self.calls = self.tmp / "calls.txt"

    def run_adapter(self, **env):
        full_env = {
            **os.environ,
            "OPENCLAW_BIN": str(self.stub),
            "JQ_BIN": shutil.which("jq"),
            "STUB_CALLS": str(self.calls),
            "STUB_FAIL_MODELS": "",
            "STUB_EMPTY_MODELS": "",
            **env,
        }
        for name in ("OPENCLAW_MODEL", "OPENCLAW_FALLBACK_MODELS"):
            if name not in env:
                full_env.pop(name, None)
        return subprocess.run([ADAPTER, self.prompt, self.log, "test"],
                              text=True, capture_output=True, env=full_env)

    def called_models(self):
        return self.calls.read_text().split()

    def test_shell_syntax(self):
        self.assertEqual(subprocess.run(["bash", "-n", ADAPTER]).returncode, 0)

    def test_primary_success_does_not_call_fallback(self):
        result = self.run_adapter()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "summary by openai/gpt-5.6-luna")
        self.assertEqual(self.called_models(), ["openai/gpt-5.6-luna"])

    def test_primary_failure_uses_fallback_and_logs_it(self):
        result = self.run_adapter(STUB_FAIL_MODELS="openai/gpt-5.6-luna")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "summary by anthropic/claude-haiku-4-5")
        self.assertEqual(self.called_models(), ["openai/gpt-5.6-luna", "anthropic/claude-haiku-4-5"])
        log = self.log.read_text()
        self.assertIn("summarize failed with model: openai/gpt-5.6-luna", log)
        self.assertIn("summarized with fallback model: anthropic/claude-haiku-4-5", log)

    def test_empty_primary_answer_uses_fallback_without_partial_output(self):
        result = self.run_adapter(STUB_EMPTY_MODELS="openai/gpt-5.6-luna")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "summary by anthropic/claude-haiku-4-5")

    def test_all_models_failing_exits_nonzero_with_empty_output(self):
        result = self.run_adapter(STUB_FAIL_MODELS="openai/gpt-5.6-luna anthropic/claude-haiku-4-5")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")

    def test_empty_fallback_list_disables_fallback(self):
        result = self.run_adapter(STUB_FAIL_MODELS="openai/gpt-5.6-luna", OPENCLAW_FALLBACK_MODELS="")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.called_models(), ["openai/gpt-5.6-luna"])

    def test_model_overrides_are_respected_in_order(self):
        result = self.run_adapter(OPENCLAW_MODEL="a/one", OPENCLAW_FALLBACK_MODELS="b/two c/three",
                                  STUB_FAIL_MODELS="a/one b/two")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "summary by c/three")
        self.assertEqual(self.called_models(), ["a/one", "b/two", "c/three"])


if __name__ == "__main__":
    unittest.main()
