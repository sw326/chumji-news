import itertools
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import review_order as r


def item(id, prediction='editorial', day=1):
    return {'id': id, 'prediction': prediction, 'committed_at': f'2026-01-{day:02}T00:00:00+00:00',
            'before': 'abc', 'after': 'defg', 'source_url': 'https://example.org',
            'commit_url': 'https://example.org', 'file': 'doc.md'}


class ReviewOrderTests(unittest.TestCase):
    def test_priority_retains_all_and_stable_ties(self):
        items = [item('b', 'risk', 2), item('a', 'unresolved'), item('d'), item('c', 'substantive')]
        q = r.orders(items)
        self.assertEqual([i['id'] for i in q['jev_priority']], ['a', 'b', 'c', 'd'])
        self.assertEqual({i['id'] for i in q['chronological']}, {'a', 'b', 'c', 'd'})

    def test_gold_not_used_for_ranking(self):
        items = [dict(item('a'), expected='risk'), dict(item('b', 'risk'), expected='editorial')]
        self.assertEqual(r.orders(items)['jev_priority'][0]['id'], 'b')

    def test_unknown_or_duplicate_refused(self):
        for items in ([item('a'), item('a')], [item('a', 'approved')]):
            with self.assertRaises(ValueError): r.orders(items)

    def test_metrics_account_for_unequal_text(self):
        items = [item('a'), dict(item('b'), after='x'*20), item('c')]
        m = r.metrics(items, {'a', 'b'})
        self.assertEqual(m['last_risk_position'], 2)
        self.assertEqual(m['characters_until_last_risk'], 30)
        self.assertEqual(m['total_characters'], 37)

    def test_random_formula_matches_exhaustive_permutations(self):
        positions = [max(p.index('a'), p.index('b')) + 1 for p in itertools.permutations('abcde')]
        self.assertEqual(sum(positions)/len(positions), r.random_expectation(5, 2)['last_risk_position'])
        self.assertIsNone(r.random_expectation(5, 0)['last_risk_position'])

    def test_fences_and_no_gold_in_packet(self):
        i = dict(item('a'), before='```\n<script>bad</script>\n```', expected='SECRET_GOLD', rationale='SECRET_REASON')
        p = r.packet([i], 'test')
        self.assertIn('````text', p)
        self.assertNotIn('SECRET', p)
        self.assertNotIn('Jev 분류', p)

    def test_missing_risk_or_duplicate_queue_refused(self):
        for queue, risks in [([item('a')], {'b'}), ([item('a'), item('a')], {'a'})]:
            with self.assertRaises(ValueError): r.metrics(queue, risks)

    def test_modified_manifest_rejected_before_validation(self):
        with tempfile.TemporaryDirectory() as d, patch.object(r.change_review, 'validate') as validate:
            root = Path(d)
            (root/'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'manifest'): r.load_items(root, root)
            validate.assert_not_called()

    def test_changed_responses_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as d, patch.object(r.claims, 'digest', side_effect=[r.SOURCE_SHA, 'tampered']), patch.object(r.claims, 'read_results') as read:
            root = Path(d)
            (root/'manifest.json').write_text('{}')
            (root/'results.jsonl').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'responses'): r.load_items(root, root)
            read.assert_not_called()


if __name__ == '__main__': unittest.main()
