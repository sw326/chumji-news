import copy
import hashlib
import unittest
import dedup
import shadow
from challenge import encoded


def snapshot(url, text=''):
    return {'url': url, 'status': 200, 'text': text}


class SourceFirstTests(unittest.TestCase):
    def setUp(self):
        self.state = {'A': {'title': 'A', 'summary': 'Existing facts'},
                      'B': {'title': 'B', 'summary': 'New facts'}}
        self.sources = {'A': snapshot('https://a.example/post'), 'B': snapshot('https://b.example/post')}

    def test_recognized_title_link_groups_without_touching_semantics_or_inputs(self):
        self.sources['A'] = snapshot('https://news.hada.io/topic?id=1', '▲\n\n[**A**](https://b.example/post?utm_source=x)(b.example)\n')
        before = copy.deepcopy((self.state, self.sources))
        r = shadow.route(self.state, self.sources, {})
        self.assertEqual(r['route'], 'code_source_group')
        self.assertIsNone(r['semantic_relation'])
        self.assertTrue(r['retain_B']); self.assertFalse(r['jev_needed'])
        self.assertEqual(before, (self.state, self.sources))

    def test_body_citation_and_imposter_domain_do_not_group(self):
        text = '[**A**](https://b.example/post)(b.example)\nArticle cites https://b.example/post'
        self.sources['A'] = snapshot('https://news.hada.io/topic?id=1', text)
        self.assertEqual(shadow.route(self.state, self.sources, {})['route'], 'jev_candidate')
        self.sources['A'] = snapshot('https://news.hada.io.attacker.example/topic?id=1', '▲\n\n'+text)
        self.assertEqual(shadow.route(self.state, self.sources, {})['route'], 'jev_candidate')

    def test_query_versions_are_distinct_and_invalid_port_fails_closed(self):
        self.sources['A'] = snapshot('https://a.example/post?v=1')
        self.sources['B'] = snapshot('https://a.example/post?v=2')
        self.assertEqual(shadow.route(self.state, self.sources, {})['route'], 'jev_candidate')
        self.sources['B'] = snapshot('https://a.example:invalid/post')
        self.assertEqual(shadow.route(self.state, self.sources, {})['route'], 'review')

    def test_missing_excerpt_does_not_trigger_jev(self):
        self.state['B']['summary'] = ''
        r = shadow.route(self.state, self.sources, {})
        self.assertEqual(r['reason'], 'missing_url_or_excerpt'); self.assertFalse(r['jev_needed'])

    def test_only_exact_input_replays_and_all_items_retained(self):
        key = hashlib.sha256(encoded(dedup.body(self.state))).hexdigest()
        cache = {key: {'status': 'ok', 'relation': 'followup', 'probabilities':
                 {'duplicate': 0, 'followup': 1, 'distinct': 0, 'unknown': 0}}}
        r = shadow.route(self.state, self.sources, cache)
        self.assertEqual(r['semantic_relation'], 'followup'); self.assertTrue(r['retain_B'])
        self.state['B']['summary'] += ' changed'
        r = shadow.route(self.state, self.sources, cache)
        self.assertIsNone(r['semantic_relation']); self.assertEqual(r['reason'], 'no_valid_matching_response')

    def test_error_or_bad_distribution_not_replayed_as_success(self):
        key = hashlib.sha256(encoded(dedup.body(self.state))).hexdigest()
        for previous in [{'status': 'error'}, {'status': 'ok', 'relation': 'duplicate', 'probabilities': {'duplicate': 1}}]:
            r = shadow.route(self.state, self.sources, {key: previous})
            self.assertIsNone(r['semantic_relation']); self.assertTrue(r['retain_B'])

    def test_multiple_headings_and_invalid_target_fail_closed(self):
        line = '▲\n\n[**A**](https://b.example/post)(b.example)\n'
        for text in [line + line, '▲\n\n[**A**](https://[bad/post)(bad)\n']:
            s = snapshot('https://news.hada.io/topic?id=1', text)
            self.assertEqual(shadow.source_identity(s)['method'], 'article_url')


if __name__ == '__main__': unittest.main()
