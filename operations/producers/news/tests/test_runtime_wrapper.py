import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WRAPPER = ROOT / "run_profile.sh"


class RuntimeWrapperTests(unittest.TestCase):
    def test_shell_syntax(self):
        self.assertEqual(subprocess.run(["bash", "-n", WRAPPER]).returncode, 0)

    def test_invalid_profile_has_no_side_effects(self):
        result = subprocess.run([WRAPPER, "invalid"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_invalid_mode_is_rejected_before_collection(self):
        result = subprocess.run([WRAPPER, "morning", "--invalid"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid mode", result.stderr)
