"""Exercise the runner with a local collector and no external publication."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'run_price_snapshot.sh'


class ReleaseStagingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'release'
        self.runner = self.root / 'operations/producers/prices/run_price_snapshot.sh'
        self.runner.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, self.runner)
        collector = self.root / 'operations/jobs/fresh-food/run_shadow.py'
        collector.parent.mkdir(parents=True)
        collector.write_text('''import datetime, json, pathlib, sys
out = pathlib.Path(sys.argv[sys.argv.index('--output-root') + 1])
date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')
run = out / date
run.mkdir(parents=True, exist_ok=True)
snapshot = run / 'snapshot.html'
snapshot.write_text('fixture graph')
(run / 'shadow-status.json').write_text(json.dumps({'collector_exit_code': 0, 'error_count': 0, 'snapshot_path': str(snapshot)}))
(run / 'report.json').write_text(json.dumps({'generatedAt': date}))
''')
        (self.root / 'package.json').write_text('{"name":"staging-fixture"}')
        self.ref = self.base / 'dummy-ref'
        self.ref.write_text('fixture-not-a-credential')
        self.env = os.environ | {
            'FRESH_PRICE_PYTHON': sys.executable,
            'FRESH_PRICE_OUTPUT_ROOT': str(self.base / 'output'),
            'FRESH_PRICE_DATA_KEY_FILE': str(self.ref),
            'FRESH_PRICE_GARAK_PASSWORD_FILE': str(self.ref),
            'FRESH_PRICE_VERCEL_PROJECT_FILE': str(self.ref),
        }

    def run_script(self, *args):
        return subprocess.run(['bash', str(self.runner), *args], env=self.env,
                              cwd=self.base, capture_output=True, text=True)

    def test_archive_release_dry_run(self):
        result = self.run_script('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dry-run: publication disabled', result.stdout)
        self.assertFalse((self.root / 'public').exists())

    def check_stage(self):
        for name in ['.env.local', '.git/config', '.next/cache', 'node_modules/private', '.vercel/auth.json']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('must-not-be-staged')
        # .git is not a real repository; a broken checkout must not silently fall back.
        shutil.rmtree(self.root / '.git')
        vercel = self.base / 'vercel'
        vercel.write_text('''#!/usr/bin/env python3
import pathlib, sys
root = pathlib.Path.cwd()
assert (root / 'package.json').is_file()
assert (root / 'public/fresh-food/index.html').read_text() == 'fixture graph'
assert len(list((root / 'public/fresh-food').glob('*/index.html'))) == 1
for name in ['.env.local', '.git', '.next', 'node_modules', '.vercel/auth.json']:
    assert not (root / name).exists(), name
print('stage-verified', flush=True)
sys.exit(70)  # stop before any external publication
''')
        vercel.chmod(0o755)
        self.env['FRESH_PRICE_VERCEL'] = str(vercel)
        result = self.run_script()
        self.assertEqual(result.returncode, 70, result.stderr)
        self.assertIn('stage-verified', result.stdout)
        self.assertFalse((self.root / 'public').exists())

    def test_archive_release_stages_only_deployable_files(self):
        self.check_stage()

    def test_git_checkout_dry_run(self):
        for args in [['init', '-q'], ['add', '.'], ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture']]:
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)
        result = self.run_script('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_broken_git_checkout_fails_closed(self):
        (self.root / '.git').mkdir()
        result = self.run_script('--dry-run')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('dry-run: publication disabled', result.stdout)


if __name__ == '__main__':
    unittest.main()
