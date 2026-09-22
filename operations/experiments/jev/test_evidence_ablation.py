import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import claims
import evidence_ablation as ablation


class EvidenceAblationTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        prior, cases, labels, sources = [], [], [], {}
        for id in sorted(ablation.PAIR_IDS):
            claim, evidence, addition = 'Claim ' + id, 'Evidence ' + id, 'Addition ' + id
            text = claim + '\n' + evidence + '\n' + addition
            src = root / (id + '.txt')
            src.write_text(text)
            a, b = len(claim) + 1, len(claim) + 1 + len(evidence)
            sources[id] = {'path': str(src), 'url': 'https://example.org',
                           'snapshot_sha256': claims.digest(text.encode())}
            state = {'claim': 'Doc\n\n' + claim, 'evidence': evidence}
            expected = 'conflict' if id == 'H15' else 'supported' if id == 'H17' else None if id == 'H20' else 'partial'
            allowed = [expected] if expected else ['supported', 'partial']
            prior.append({'id': id, 'source': id, 'claim_span': [0, len(claim)],
                          'claim_context': 'Doc', 'state': state,
                          'expected': expected, 'acceptable_labels': allowed})
            for variant in sorted(ablation.VARIANTS):
                seg = [{'source': id, 'span': [a, b]}]
                current = state.copy()
                ex, al = expected, allowed
                if variant == 'enriched':
                    seg.append({'source': id, 'span': [b + 1, len(text)]})
                    current['evidence'] += '\n\n' + addition
                    ex = 'conflict' if id == 'H15' else 'supported'
                    al = [ex]
                cases.append({'id': id + '-' + variant, 'pair_id': id, 'variant': variant,
                              'claim_source': id, 'claim_span': [0, len(claim)],
                              'claim_context': 'Doc', 'segments': seg, 'state': current})
                labels.append({'id': id + '-' + variant, 'expected': ex,
                               'acceptable_labels': al, 'rationale': 'offline test'})
        prior_path = root / 'prior.json'
        prior_path.write_text(json.dumps({'cases': prior}))
        digest = claims.digest(prior_path.read_bytes())
        patcher = patch.object(ablation, 'EXPECTED_PRIOR_SHA', digest)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cp, self.lp = root / 'corpus.json', root / 'labels.json'
        self.cp.write_text(json.dumps({'issue': 'https://github.com/sw326/chumji-wiki/issues/22',
                                      'prior_manifest_path': str(prior_path), 'prior_manifest_sha256': digest,
                                      'sources': sources, 'cases': cases}))
        self.lp.write_text(json.dumps({'cases': labels}))
        cat = {'data': [{'id': claims.runner.MODELS['jev'], 'pricing': {'input': '0.000000042', 'output': '0'}}]}
        self.out = root / 'out'
        with patch('urllib.request.urlopen', return_value=io.StringIO(json.dumps(cat))), contextlib.redirect_stdout(io.StringIO()):
            ablation.prepare(self.out, self.cp, self.lp)

    def test_scope_only_jev_and_no_labels(self):
        m = ablation.validate(self.out)
        self.assertEqual(m['max_calls'], 12)
        self.assertEqual({t['arm'] for t in m['tasks']}, {'jev'})
        for t in m['tasks']:
            self.assertEqual(set(t['body']['state']), {'claim', 'evidence'})

    def test_extra_state_key_rejected_before_catalog(self):
        c = json.loads(self.cp.read_text())
        c['cases'][0]['state']['expected'] = 'supported'
        self.cp.write_text(json.dumps(c))
        with patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'Unexpected state keys'):
                ablation.prepare(self.out.parent / 'bad', self.cp, self.lp)
            network.assert_not_called()

    def test_rehashed_label_change_rejected(self):
        m = ablation.validate(self.out)
        m['cases'][0]['expected'] = 'supported'
        raw = claims.runner.encoded(m)
        (self.out / 'manifest.json').write_bytes(raw)
        (self.out / 'manifest.sha256').write_text(claims.digest(raw))
        with self.assertRaisesRegex(ValueError, 'Case or label differs'):
            ablation.validate(self.out)

    def test_nonappend_enrichment_rejected(self):
        c = json.loads(self.cp.read_text())
        enriched = next(x for x in c['cases'] if x['variant'] == 'enriched')
        enriched['segments'] = enriched['segments'][1:]
        enriched['state']['evidence'] = enriched['state']['evidence'].split('\n\n')[1]
        self.cp.write_text(json.dumps(c))
        with patch('urllib.request.urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'append-only'):
                ablation.prepare(self.out.parent / 'bad', self.cp, self.lp)
            network.assert_not_called()

    def test_excess_limit_blocks_network(self):
        with patch.object(claims.runner, 'execute') as network:
            with self.assertRaisesRegex(ValueError, 'Invalid limit'):
                claims.execute(self.out, 13, False, validator=ablation.validate)
            network.assert_not_called()

    def test_rehashed_decision_policy_change_rejected(self):
        m = ablation.validate(self.out)
        m['decision_policy']['deployment_authorized'] = True
        raw = claims.runner.encoded(m)
        (self.out / 'manifest.json').write_bytes(raw)
        (self.out / 'manifest.sha256').write_text(claims.digest(raw))
        with self.assertRaisesRegex(ValueError, 'Contract changed'):
            ablation.validate(self.out)

    def fake_results(self, conflict_label):
        m = ablation.validate(self.out)
        cases = {c['id']: c for c in m['cases']}
        rows = []
        for task in m['tasks']:
            label = cases[task['id']]['acceptable_labels'][0]
            if task['id'] == 'H15-enriched':
                label = conflict_label
            rows.append({'id': task['id'], 'arm': 'jev', 'request_sha256': task['sha256'],
                         'status': 'ok', 'topic': label, 'latency_ms': 1,
                         'reported_cost_usd': 0, 'list_cost_usd': 0,
                         'response': {'answers': {'topic': {'type': 'choice', 'choice': label,
                             'probabilities': {k: int(k == label) for k in claims.CRITERIA}}},
                             'usage': {'inputTokens': 1, 'outputTokens': 0}}})
        (self.out / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def test_missed_enriched_conflict_stops(self):
        self.fake_results('supported')
        with contextlib.redirect_stdout(io.StringIO()):
            ablation.report(self.out)
        s = json.loads((self.out / 'summary.json').read_text())
        self.assertEqual(s['decision'], 'stop_this_wiki_claim_checker_adoption_experiment')

    def test_unresolved_conflict_or_unattempted_holds(self):
        with contextlib.redirect_stdout(io.StringIO()):
            ablation.report(self.out)
        self.assertEqual(json.loads((self.out / 'summary.json').read_text())['decision'], 'hold_no_extra_calls')
        self.fake_results('partial')
        with contextlib.redirect_stdout(io.StringIO()):
            ablation.report(self.out)
        self.assertEqual(json.loads((self.out / 'summary.json').read_text())['decision'], 'hold_no_extra_calls')


if __name__ == '__main__':
    unittest.main()
