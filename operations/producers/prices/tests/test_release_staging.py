"""Run the real wrapper without any network, deployment, or notification."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


class DurablePublicationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'release'
        for name in ['operations/producers/prices/run_price_snapshot.sh',
                     'scripts/price-artifacts.mjs', 'src/lib/price-artifact.mjs']:
            dest = self.root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, dest)
        self.runner = self.root / 'operations/producers/prices/run_price_snapshot.sh'
        collector = self.root / 'operations/jobs/fresh-food/run_shadow.py'
        collector.parent.mkdir(parents=True)
        collector.write_text('''import datetime, hashlib, json, pathlib, sys
out = pathlib.Path(sys.argv[sys.argv.index('--output-root') + 1])
date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d')
run = out / date
run.mkdir(parents=True, exist_ok=True)
snapshot = run / 'snapshot.html'
snapshot.write_text('<html><body>fixture graph</body></html>')
report = run / 'report.json'
report.write_text(json.dumps({'generatedAt': date}))
(run / 'shadow-status.json').write_text(json.dumps({'collector_exit_code': 0, 'error_count': 0,
'snapshot_path': str(snapshot), 'snapshot_sha256': hashlib.sha256(snapshot.read_bytes()).hexdigest(),
'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest()}))
''')
        self.ref = self.base / 'dummy-ref'
        self.ref.write_text('# fixture-only\n')
        self.env = os.environ | {
            'FRESH_PRICE_PYTHON': sys.executable,
            'FRESH_PRICE_NODE': shutil.which('node'),
            'FRESH_PRICE_OUTPUT_ROOT': str(self.base / 'output'),
            'FRESH_PRICE_DATA_KEY_FILE': str(self.ref),
            'FRESH_PRICE_GARAK_PASSWORD_FILE': str(self.ref),
            'FRESH_PRICE_APP_ENV_FILE': str(self.ref),
            'FRESH_PRICE_TELEGRAM_TOKEN_FILE': str(self.base / 'intentionally-absent'),
        }

    def run_script(self, *args):
        return subprocess.run(['bash', str(self.runner), *args], env=self.env,
                              cwd=self.base, capture_output=True, text=True)

    def test_archive_release_dry_run_without_credentials_or_deploy_files(self):
        result = self.run_script('--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('dry-run: publication disabled', result.stdout)
        self.assertFalse((self.root / 'public').exists())

    def test_invalid_collector_hash_stops_even_dry_run(self):
        collector = self.root / 'operations/jobs/fresh-food/run_shadow.py'
        collector.write_text(collector.read_text() + '\nsnapshot.write_text("changed")\n')
        result = self.run_script('--dry-run')
        self.assertNotEqual(result.returncode, 0)

    def test_upload_or_public_hash_failure_stops_before_summary_and_telegram(self):
        for fail in ['upload', 'verify']:
            node = self.base / 'fake-node'
            node.write_text(f'''#!{sys.executable}
import os, sys
args = sys.argv[1:]
if args[0].endswith('price-artifacts.mjs') and '--publish' not in args:
    os.execv({shutil.which('node')!r}, [{shutil.which('node')!r}, *args])
if '--publish' in args:
    print('upload', flush=True)
    sys.exit(71 if {fail!r} == 'upload' else 0)
if args[0].endswith('verify-price-artifact.mjs'):
    print('verify', flush=True)
    sys.exit(72)
raise SystemExit('unexpected summary/notification call')
''')
            node.chmod(0o755)
            self.env['FRESH_PRICE_NODE'] = str(node)
            result = self.run_script()
            self.assertEqual(result.returncode, 71 if fail == 'upload' else 72, result.stderr)
            self.assertNotIn('publication complete', result.stdout)
            self.assertEqual('verify' in result.stdout, fail == 'verify')


if __name__ == '__main__':
    unittest.main()
