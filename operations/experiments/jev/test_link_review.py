import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import actions as a
import link_review as l
import sequential as s


def synthetic_store():
    # Deliberately scripted choices, NOT Jev responses or accuracy evidence.
    records=[];previous=None
    for i,(title,text,choice) in enumerate([
        ('Mission A launch','A launches','create_event'),
        ('Mission B launch','B launches','create_event'),
        ('Mission A update','A lands but deliberately assigned to B','wrong'),
        ('Mission B update','B followup observes contaminated candidate','follow'),
        ('Unrelated report','Unique topic','create_event')],1):
        article={'id':f'a{i}','title':title,'text':text,'url':f'https://example.org/{i}'}
        initial=s.fresh_news({'incoming':article},previous);view=a.news_view(initial)
        if choice in ('wrong','follow'):
            slot=next(c['slot'] for c in view['candidates'] if c['id']=='new-a2')
            choice=f'update_{slot}'
        previous=a.transition('news',initial,choice,view)
        records.append({'article':article,'view':view,'history':{'before_sha256':a.hash_obj(initial),'action':choice,'receipt':previous['receipt'],'decision':{'origin':'scripted_fault','valid':True}},'request':None,'response':None})
    base={'records':records,'source':'synthetic_fault_injection','fixture_sha256':None}
    return {'version':1,'base':base,'base_sha256':a.hash_obj(base),'corrections':[]}


def request(ident,mode='move',article='a3',target='new-a1',relation='update'):
    return {'id':ident,'mode':mode,'article_id':article,'target':target,'relation':relation,'actor':'test-reviewer','reason':'Scripted fault correction'}


class LinkReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'store.json';self.store=synthetic_store();a.exclusive(self.path,self.store)

    def test_move_repairs_content_preserves_evidence_and_other_links(self):
        old=l.projection(self.store)
        new=l.correct(self.path,a.hash_obj(self.store),request('fix'))
        result=l.projection(new)
        self.assertEqual(new['base'],self.store['base'])
        self.assertEqual(result['assignments']['a3'],{'event_id':'new-a1','relation':'update'})
        for aid in ('a1','a2','a4','a5'):self.assertEqual(result['assignments'][aid],old['assignments'][aid])
        b=next(e for e in result['events'] if e['id']=='new-a2')
        self.assertNotIn('deliberately assigned',b['text'])
        self.assertNotIn('a3',b['article_ids']);self.assertNotIn('a3',b['update_ids'])
        self.assertIn('a4',result['review_required']);self.assertNotIn('a5',result['review_required'])
        self.assertEqual(result['retrieval_recheck_ids'],['a4','a5'])
        self.assertIn('deliberately assigned',str(l.inspect(new,'a4')['evidence'][0]['view']))

    def test_unlink_split_and_restore_preserve_all_versions(self):
        state=l.correct(self.path,a.hash_obj(self.store),request('unlink','unlink',target=None,relation=None))
        self.assertIn('a3',l.projection(state)['unlinked_ids'])
        state=l.correct(self.path,a.hash_obj(state),request('split','split',target=None,relation=None))
        self.assertEqual(l.projection(state)['assignments']['a3']['event_id'],'manual-split')
        state=l.correct(self.path,a.hash_obj(state),request('restore',target='new-a2'))
        self.assertEqual(l.projection(state)['assignments'],l.projection(self.store)['assignments'])
        self.assertEqual(len(state['corrections']),3)
        self.assertEqual(state['base'],self.store['base'])

    def test_replay_stale_unknown_target_and_id_reuse(self):
        req=request('fix');state=l.correct(self.path,a.hash_obj(self.store),req);raw=self.path.read_bytes()
        self.assertEqual(l.correct(self.path,a.hash_obj(self.store),req),state)
        self.assertEqual(self.path.read_bytes(),raw)
        for sha,req in [(a.hash_obj(self.store),request('stale')),(a.hash_obj(state),request('bad',target='missing')),(a.hash_obj(state),request('fix',target='new-a2'))]:
            with self.assertRaises(ValueError):l.correct(self.path,sha,req)
            self.assertEqual(self.path.read_bytes(),raw)

    def test_seed_removal_rebuilds_event_title_and_text(self):
        state=l.correct(self.path,a.hash_obj(self.store),request('seed','unlink',article='a2',target=None,relation=None))
        event=next(e for e in l.projection(state)['events'] if e['id']=='new-a2')
        self.assertNotIn('B launches',event['text']);self.assertEqual(event['title'],'Mission A update')

    def test_moving_older_member_does_not_replace_existing_seed(self):
        state=l.correct(self.path,a.hash_obj(self.store),request('older',article='a1',target='new-a2',relation='member'))
        event=next(e for e in l.projection(state)['events'] if e['id']=='new-a2')
        self.assertEqual(event['title'],'Mission B launch')
        self.assertIn('B launches',event['text'])
        self.assertNotIn('A launches',event['text'])
        self.assertIn('a1',event['article_ids'])

    def test_failed_atomic_replace_preserves_store(self):
        raw=self.path.read_bytes()
        with patch.object(l.os,'replace',side_effect=OSError('injected disk failure')):
            with self.assertRaises(OSError):l.correct(self.path,a.hash_obj(self.store),request('fix'))
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertFalse(list(self.path.parent.glob('*.tmp')))

    def test_import_decision_contract_rejects_false_origin_or_metadata(self):
        initial=s.fresh_news({'incoming':{'id':'x','title':'Empty','text':'','url':'https://example.org/x'}})
        h={'action':'defer','decision':{'origin':'code','valid':True}}
        l.validate_decision(initial,h,None)
        h['decision']['origin']='scripted_fault'
        with self.assertRaisesRegex(ValueError,'origin'):l.validate_decision(initial,h,None)
        h={'action':'defer','decision':{'origin':'jev','raw_action':None,'valid':False,'fallback_reason':'api_error'}}
        l.validate_decision(initial,h,{'status':'error'})
        h['decision']['valid']=True
        with self.assertRaisesRegex(ValueError,'metadata'):l.validate_decision(initial,h,{'status':'error'})
        h={'action':'create_event','decision':{'origin':'code','valid':True}}
        with self.assertRaisesRegex(ValueError,'deterministic'):l.validate_decision(initial,h,None)

    def test_base_and_chain_drift_fail(self):
        changed=copy.deepcopy(self.store);changed['base']['records'][0]['article']['text']='tampered'
        with self.assertRaisesRegex(ValueError,'Frozen'):l.validate(changed)
        changed=l.correct(self.path,a.hash_obj(self.store),request('fix'))
        changed['corrections'][0]['before']['event_id']='other'
        with self.assertRaisesRegex(ValueError,'before-state'):l.validate(changed)


if __name__=='__main__':unittest.main()
