import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import enrich
from challenge import encoded


class ContinuationTests(unittest.TestCase):
    def fixture(self, out):
        cases = [{'id': str(i), 'request_sha256': str(i)} for i in range(17)]
        raw = encoded({'cases': cases})
        (out / 'manifest.json').write_bytes(raw)
        (out / 'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest())
        (out / 'results.jsonl').write_text(json.dumps({'id': '0', 'request_sha256': '0', 'status': 'error', 'http_status': 503}) + '\n')
        (out / 'run.json').write_text(json.dumps({'reported_cost_usd': 0, 'reference_cost_usd': 0}))

    def test_failed_attempt_never_retried_and_continuation_exclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); self.fixture(out)
            enrich.continue_prepare(out)
            cases = json.loads((out / 'continuation/manifest.json').read_text())['cases']
            self.assertEqual(len(cases), 16)
            self.assertNotIn('0', [c['id'] for c in cases])
            with self.assertRaises(FileExistsError): enrich.continue_prepare(out)

    def test_tampered_original_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); self.fixture(out)
            with (out / 'manifest.json').open('a') as f: f.write(' ')
            with self.assertRaisesRegex(ValueError, 'changed'): enrich.continue_prepare(out)
            self.assertFalse((out / 'continuation').exists())

    def test_unavailable_source_rejected_before_extracting(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            enrich.excerpt({'id': 'R01A', 'text': '', 'status': 503})


if __name__ == '__main__': unittest.main()
