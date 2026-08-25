import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

JOB_DIR = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("global_intel_fetch_acled", JOB_DIR / "fetch_acled.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AcledCredentialLoadingTest(unittest.TestCase):
    def tearDown(self):
        os.environ.pop("ACLED_EMAIL", None)
        os.environ.pop("ACLED_PASSWORD", None)

    def test_unreadable_legacy_path_does_not_break_import_or_loading(self):
        with mock.patch.object(Path, "read_text", side_effect=PermissionError):
            MODULE.load_credentials(Path("/unreadable/legacy.env"))

    def test_explicit_secret_file_overwrites_stale_values(self):
        os.environ["ACLED_EMAIL"] = "old@example.com"
        os.environ["ACLED_PASSWORD"] = "old"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "acled.env"
            path.write_text(
                "ACLED_EMAIL=new@example.com\nACLED_PASSWORD=new-password\n"
            )
            MODULE.load_credentials(path, overwrite=True)
        self.assertEqual(os.environ["ACLED_EMAIL"], "new@example.com")
        self.assertEqual(os.environ["ACLED_PASSWORD"], "new-password")


if __name__ == "__main__":
    unittest.main()
