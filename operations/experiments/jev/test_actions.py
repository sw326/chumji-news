import copy
import json
from pathlib import Path
import tempfile
import unittest
import actions as a

class ControllerTests(unittest.TestCase):
    def news(self):
        article={'id':'old','url':'https://example.org/a','title':'Release','text':'Atlas release'}
        return {'status':'active','incoming':{**article,'id':'new','url':'https://example.org/b'},
                'events':[{'id':'e1','title':'Release','text':'Atlas release','article_ids':['old'],'update_ids':[]}],
                'articles':[article],'deferred_ids':[],'actions':[]}
    def docs(self):
        return [{'id':'a','title':'SQLite','text':'Connection defaults','links':['b'],'index':'primary','url':'https://example.org/a'},
                {'id':'b','title':'SQLite transaction','text':'No effect inside transaction','links':['a'],'index':'primary','url':'https://example.org/b'},
                {'id':'c','title':'JSON','text':'JSON escaping exceptions','links':[],'index':'secondary','url':'https://example.org/c'}]
    def search(self):
        return {'status':'active','query':'SQLite transaction','found_ids':['a'],'actions':[],'other_index_used':False}
    def test_attach_preserves_both_articles(self):
        s=self.news(); r=a.transition('news',s,'attach_0',a.news_view(s))
        self.assertEqual(r['events'][0]['article_ids'],['old','new']); self.assertEqual(len(r['articles']),2)
        self.assertEqual(len(s['articles']),1)
    def test_update_retains_prior_and_new_facts(self):
        s=self.news(); s['incoming']['text']='Atlas release delayed'
        r=a.transition('news',s,'update_0',a.news_view(s))
        self.assertEqual(r['events'][0]['update_ids'],['new']); self.assertIn('Atlas release\n\nAtlas release delayed',r['events'][0]['text'])
    def test_create_does_not_overwrite_event(self):
        s=self.news(); r=a.transition('news',s,'create_event',a.news_view(s))
        self.assertEqual(len(r['events']),2); self.assertEqual(r['events'][0],s['events'][0])
    def test_defer_keeps_original(self):
        s=self.news(); r=a.transition('news',s,'defer',a.news_view(s)); self.assertEqual(r['deferred_ids'],['new']); self.assertEqual(len(r['articles']),2)
    def test_absent_candidate_rejected(self):
        s=self.news()
        with self.assertRaisesRegex(ValueError,'Unavailable'): a.transition('news',s,'attach_2',a.news_view(s))
    def test_same_url_changed_content_not_code_duplicate(self):
        s=self.news(); s['incoming']['url']=s['articles'][0]['url']
        self.assertEqual(a.exact_news_action(s,a.news_view(s)),'attach_0')
        s['incoming']['text']+=' corrected'
        self.assertIsNone(a.exact_news_action(s,a.news_view(s)))
    def test_atomic_receipt_replay_and_stale_state_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'state.json'; s=self.news(); a.exclusive(p,s); view=a.news_view(s)
            a.commit_action(p,a.hash_obj(s),'news','attach_0',view)
            with self.assertRaisesRegex(ValueError,'Stale'): a.commit_action(p,a.hash_obj(s),'news','attach_0',view)
            self.assertEqual(len(a.read(p)['articles']),2)
    def test_view_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'state.json';s=self.news();a.exclusive(p,s);v=a.news_view(s);v['candidates'][0]['id']='other'
            with self.assertRaisesRegex(ValueError,'Candidate'):a.commit_action(p,a.hash_obj(s),'news','attach_0',v)
    def test_link_reads_document_and_prevents_cycle(self):
        s=self.search();d=self.docs();v=a.search_view(s,d)
        r=a.transition('search',s,'expand_linked_pages',v,d)
        self.assertEqual(r['found_ids'],['a','b']); self.assertEqual(a.search_view(r,d)['unvisited_links'],[])
        end=a.transition('search',r,'return_candidates',a.search_view(r,d),d)
        self.assertEqual(end['packet'][1]['text'],'No effect inside transaction')
    def test_other_index_real_query_and_no_repeat(self):
        s=self.search();s['query']='JSON';d=self.docs()
        r=a.transition('search',s,'search_other_index',a.search_view(s,d),d)
        self.assertEqual(r['found_ids'],['a','c']);self.assertNotIn('search_other_index',a.search_view(r,d)['available_actions'])
    def test_no_hit_returns_empty_then_handoff(self):
        s=self.search();s['query']='BYPASSRLS';d=self.docs()
        r=a.transition('search',s,'search_other_index',a.search_view(s,d),d)
        self.assertEqual(r['receipt']['added_ids'],[])
        end=a.transition('search',r,'handoff_to_research',a.search_view(r,d),d)
        self.assertEqual(end['research_queue'][0]['query'],'BYPASSRLS')
    def test_budget_removes_traversal_actions(self):
        s=self.search();s['actions']=['expand_linked_pages','search_other_index']
        self.assertEqual(a.search_view(s,self.docs())['available_actions'],['return_candidates','handoff_to_research'])
    def test_terminal_cannot_run_again(self):
        s=self.news();s['status']='done'
        with self.assertRaisesRegex(ValueError,'terminal'):a.transition('news',s,'create_event',a.news_view(s))
    def test_labels_not_in_request(self):
        s=self.news();body=a.request('news',a.news_view(s))
        self.assertNotIn('expected',json.dumps(body)); self.assertNotIn('rationale',json.dumps(body))
    def test_search_result_not_truth_claim(self):
        s=self.search(); d=self.docs();r=a.transition('search',s,'return_candidates',a.search_view(s,d),d)
        self.assertEqual(r['packet'],[d[0]]);self.assertNotIn('answer',r)

if __name__=='__main__':unittest.main()
