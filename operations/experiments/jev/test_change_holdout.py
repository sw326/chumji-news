import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import claims
import change_review as change


class RealChangeTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        sources={};cases=[];labels=[]
        for i in range(1,17):
            id=f'F{i:02}';state={};segments={}
            for variant,rev in [('before','a'*40),('after','b'*40)]:
                key=id+'-'+variant;text=f'{variant} content {id}';path=self.root/(key+'.txt');path.write_text(text)
                sources[key]={'path':str(path),'snapshot_sha256':claims.digest(text.encode()),'repo':'mdn/content',
                    'file':id+'.md','commit':rev,'parent_commit':'a'*40,'after_commit':'b'*40,
                    'url':'https://raw.githubusercontent.com/mdn/content/'+rev+'/'+id+'.md'}
                state[variant]=text;segments[variant]={'source':key,'span':[0,len(text)]}
            cases.append({'id':id,'group':'real_forward','state':state,'segments':segments})
            ex='risk' if i<=7 else 'editorial' if i<=12 else 'substantive' if i<=14 else None
            labels.append({'id':id,'expected':ex,'acceptable_labels':[ex] if ex else ['editorial','substantive'],'rationale':'test fixture'})
        self.corpus=self.root/'corpus.json';self.labels=self.root/'labels.json'
        self.corpus.write_text(json.dumps({'cases':cases,'sources':sources}));self.labels.write_text(json.dumps({'cases':labels}))
        self.prior=self.root/'prior.json';self.prior.write_text(json.dumps({'rules':change.RULE,'criteria':change.CRITERIA,'tasks':[]}))
        self.enterContext(patch.object(change,'PRIOR_SHA',claims.digest(self.prior.read_bytes())))
        self.out=self.root/'run'
        cat={'data':[{'id':claims.runner.MODELS['jev'],'pricing':{'input':'0.000000042','output':'0'}}]}
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(cat))),contextlib.redirect_stdout(io.StringIO()):
            change.prepare(self.out,self.corpus,self.labels,'real',self.prior)

    def corpus_audit(self, mutate):
        c=json.loads(self.corpus.read_text());l=json.loads(self.labels.read_text());s={k:Path(v['path']).read_text() for k,v in c['sources'].items()}
        mutate(c);change.audit(c,l,s,'real')

    def test_default_cannot_execute_real_scope(self):
        with self.assertRaisesRegex(ValueError,'Contract changed'):change.validate(self.out)
        self.assertEqual(change.validate(self.out,'real')['max_calls'],16)

    def test_parent_direction_and_url_guard(self):
        with self.assertRaisesRegex(ValueError,'parent direction'):self.corpus_audit(lambda c:c['sources']['F01-after'].update(parent_commit='c'*40))
        with self.assertRaisesRegex(ValueError,'URL or repository'):self.corpus_audit(lambda c:c['sources']['F01-after'].update(url='https://example.org'))

    def test_real_scope_rejects_synthetic_and_reverse_ids(self):
        with self.assertRaisesRegex(ValueError,'case scope'):self.corpus_audit(lambda c:c['cases'][0].update(id='S01'))

    def test_over_budget_blocks_runner(self):
        with patch.object(claims.runner,'execute') as run:
            with self.assertRaisesRegex(ValueError,'Invalid limit'):claims.execute(self.out,17,False,validator=lambda out:change.validate(out,'real'),criteria=change.CRITERIA)
            run.assert_not_called()

    def test_frozen_prior_tamper_rejected(self):
        (self.out/'prior-manifest.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Prior contract'):change.validate(self.out,'real')

    def test_reused_prior_input_rejected(self):
        prior=json.loads(self.prior.read_text());corpus=json.loads(self.corpus.read_text())
        prior['tasks']=[{'sha256':claims.digest(claims.runner.encoded(change.request(corpus['cases'][0]['state'])))}]
        self.prior.write_text(json.dumps(prior))
        with patch.object(change,'PRIOR_SHA',claims.digest(self.prior.read_bytes())):
            with self.assertRaisesRegex(ValueError,'Prior input reused'):change.prepare(self.root/'another',self.corpus,self.labels,'real',self.prior)

    def test_partial_and_ambiguous_reporting(self):
        with contextlib.redirect_stdout(io.StringIO()):change.report(self.out,'real')
        s=json.loads((self.out/'summary.json').read_text());self.assertEqual(s['decision'],'hold_no_extra_calls');self.assertEqual(len(s['ambiguous_cases']),2)
        m=change.validate(self.out,'real');cases={c['id']:c for c in m['cases']};rows=[]
        for t in m['tasks']:
            label=cases[t['id']]['acceptable_labels'][0]
            rows.append({'id':t['id'],'arm':'jev','request_sha256':t['sha256'],'status':'ok','topic':label,'latency_ms':1,'reported_cost_usd':0,'list_cost_usd':0,
             'response':{'answers':{'topic':{'type':'choice','choice':label,'probabilities':{k:int(k==label) for k in change.CRITERIA}}},'usage':{'inputTokens':1}}})
        (self.out/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        with contextlib.redirect_stdout(io.StringIO()):change.report(self.out,'real')
        s=json.loads((self.out/'summary.json').read_text());self.assertEqual(s['decision'],'candidate_for_offline_review_order_only');self.assertEqual(s['risk_valid'],7);self.assertEqual(s['editorial_valid'],5)
        self.assertEqual(s['groups']['real_forward']['confirmed'],14);self.assertTrue(all(x['in_acceptable'] for x in s['ambiguous_cases']))


if __name__=='__main__':unittest.main()
