import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import claims
import holdout


class HoldoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        snapshot = 'Public claim.\nSeparate public evidence.'
        source = root / 'source.txt'
        source.write_text(snapshot)
        cases = [{'id': f'H{i:02}', 'source': 'doc', 'slot': 'intro',
                  'claim_context': 'Doc', 'claim_span': [0, 13],
                  'state': {'claim': 'Doc\n\nPublic claim.', 'evidence': snapshot[14:]}}
                 for i in range(1, 31)]
        corpus = {'issue': 'https://github.com/sw326/chumji-wiki/issues/21',
                  'sources': {'doc': {'path': str(source), 'url': 'https://example.org',
                                     'snapshot_sha256': claims.digest(snapshot.encode()),
                                     'spans': [[14, len(snapshot)]], 'excerpt': snapshot[14:]}},
                  'cases': cases}
        labels = {'cases': [{'id': c['id'], 'expected': 'supported' if i < 8 else 'partial' if i < 20 else None,
                            'acceptable_labels': ['supported'] if i < 8 else ['partial'] if i < 20 else ['partial', 'supported'],
                            'rationale': 'Offline test only'} for i, c in enumerate(cases)]}
        cp, lp = root / 'corpus.json', root / 'labels.json'
        cp.write_text(json.dumps(corpus))
        lp.write_text(json.dumps(labels))
        cat = {'data': [{'id': model, 'pricing': {'input': '0.0000001', 'output': '0.0000004'}}
                        for model in claims.runner.MODELS.values()]}
        self.out = root / 'out'
        with patch('urllib.request.urlopen', return_value=io.StringIO(json.dumps(cat))), contextlib.redirect_stdout(io.StringIO()):
            holdout.prepare(self.out, cp, lp)

    def test_rehashed_fabricated_claim_rejected(self):
        m = holdout.validate(self.out)
        c = m['cases'][0]
        c['state']['claim'] = 'Invented assertion'
        for t in m['tasks']:
            if t['id'] == c['id']:
                t['body'] = claims.request(c['state'], t['arm'])
                t['sha256'] = claims.digest(claims.runner.encoded(t['body']))
        raw = claims.runner.encoded(m)
        (self.out / 'manifest.json').write_bytes(raw)
        (self.out / 'manifest.sha256').write_text(claims.digest(raw))
        with self.assertRaisesRegex(ValueError, 'Case differs from pre-call corpus'):
            holdout.validate(self.out)

    def test_rehashed_label_change_rejected(self):
        m = holdout.validate(self.out)
        m['cases'][0]['expected'] = 'conflict'
        raw = claims.runner.encoded(m)
        (self.out / 'manifest.json').write_bytes(raw)
        (self.out / 'manifest.sha256').write_text(claims.digest(raw))
        with self.assertRaisesRegex(ValueError, 'Label differs from pre-call adjudication'):
            holdout.validate(self.out)

    def test_rehashed_label_in_state_rejected(self):
        m = holdout.validate(self.out)
        c = m['cases'][0]
        c['state']['expected'] = 'supported'
        for t in m['tasks']:
            if t['id'] == c['id']:
                t['body'] = claims.request(c['state'], t['arm'])
                t['sha256'] = claims.digest(claims.runner.encoded(t['body']))
        raw = claims.runner.encoded(m)
        (self.out / 'manifest.json').write_bytes(raw)
        (self.out / 'manifest.sha256').write_text(claims.digest(raw))
        with self.assertRaisesRegex(ValueError, 'Unexpected state keys'):
            holdout.validate(self.out)

    def test_ambiguous_excluded_and_small_normal_denominator_not_pass(self):
        m = holdout.validate(self.out)
        rows = []
        for t in m['tasks']:
            if t['arm'] != 'llm':
                continue
            rows.append({'id': t['id'], 'arm': 'llm', 'request_sha256': t['sha256'],
                         'status': 'ok', 'topic': 'supported', 'latency_ms': 1,
                         'reported_cost_usd': 0, 'list_cost_usd': 0,
                         'response': {'choices': [{'finish_reason': 'stop', 'message': {
                             'content': '{"topic":"supported"}'}}],
                             'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}})
        (self.out / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
        with contextlib.redirect_stdout(io.StringIO()):
            holdout.report(self.out)
        s = json.loads((self.out / 'summary.json').read_text())
        arm = s['arms']['llm']
        self.assertEqual((arm['normal_valid'], arm['review_required_valid'], arm['ambiguous_valid']), (8, 12, 10))
        self.assertEqual(arm['exact_denominator'], 20)
        self.assertEqual(len(arm['missed_review_ids']), 12)
        self.assertEqual(arm['pilot_gate'], 'insufficient')
        self.assertEqual(s['arms']['jev']['pilot_gate'], 'incomplete')

    def test_adjudication_tamper_rejected(self):
        (self.out / 'labels-before-calls.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Pre-call record changed'):
            holdout.validate(self.out)

    def test_request_excludes_review_metadata(self):
        m = holdout.validate(self.out)
        for task in m['tasks']:
            body = task['body']
            state = body.get('state') or json.loads(body['messages'][1]['content'])
            self.assertEqual(set(state), {'claim', 'evidence'})


if __name__ == '__main__':
    unittest.main()
