import copy
import unittest
from unittest.mock import patch
import actions as a
import sequential as s


class SequentialTests(unittest.TestCase):
    def test_next_article_inherits_actual_result_not_expected_labels(self):
        first = {'incoming': {'id':'a','title':'Mission A','text':'launch','url':'https://example.org/a'}}
        before = s.fresh_news(first)
        after = a.transition('news', before, 'create_event', a.news_view(before))
        second = {'incoming': {'id':'b','title':'Mission A','text':'landed','url':'https://example.org/b'},
                  'expected': {'event_id':'different-label'}, 'events': [{'id':'gold-correction'}]}
        state = s.fresh_news(second, after)
        self.assertEqual(state['events'], after['events'])
        self.assertEqual(state['articles'], after['articles'])
        self.assertEqual(state['actions'], [])
        state['events'][0]['text'] = 'changed'
        self.assertEqual(after['events'][0]['text'], 'launch')
        self.assertNotIn('expected', a.request('news', a.news_view(state))['state'])

    def test_unfinished_stream_predecessor_is_blocked(self):
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            s.fresh_news({'incoming': {}}, {'status':'active'})

    def test_update_visible_to_later_step_and_duplicate_keeps_actual_target(self):
        c = {'incoming': {'id':'a','title':'Mission','text':'planned','url':'https://example.org/a'}}
        first = s.fresh_news(c)
        first = a.transition('news', first, 'create_event', a.news_view(first))
        second = s.fresh_news({'incoming': {**c['incoming'], 'id':'b','text':'landed'}}, first)
        second = a.transition('news', second, 'update_0', a.news_view(second))
        third = s.fresh_news({'incoming': {**second['incoming'], 'id':'c'}}, second)
        self.assertIn('landed', a.news_view(third)['candidates'][0]['text'])
        self.assertEqual(a.exact_news_action(third, a.news_view(third)), 'attach_0')
        self.assertEqual(third['events'][0]['update_ids'], ['b'])

    def test_fullscan_can_only_decide_sufficiency_not_retrieve_again(self):
        docs = [{'id':'a','title':'A','text':'A','links':['b'],'index':'primary'},
                {'id':'b','title':'B','text':'B','links':[],'index':'secondary'}]
        f = {'search': {'index_descriptions': {'secondary': {'description':'B'}}}}
        full = s.search_initial({'query':'A','initial_ids':['a','b'],'condition':'fullscan'}, f)
        routed = s.search_initial({'query':'A','initial_ids':['a'],'condition':'routed'}, f)
        self.assertEqual(a.search_view(full,docs)['available_actions'], ['return_candidates','handoff_to_research'])
        self.assertIn('expand_linked_pages', a.search_view(routed,docs)['available_actions'])
        self.assertEqual(full['tool_catalog'], routed['tool_catalog'])


if __name__ == '__main__': unittest.main()
