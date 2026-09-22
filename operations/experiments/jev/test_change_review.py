import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import claims
import change_review as change


class ChangeReviewTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name)
        sources={};cases=[];labels=[]
        for i in range(1,7):
            state={};segments={}
            for v in ('before','after'):
                key=f's{i}-{v}';text=f'{v} paragraph {i}';path=root/(key+'.txt');path.write_text(text)
                sources[key]={'path':str(path),'snapshot_sha256':claims.digest(text.encode())}
                state[v]=text;segments[v]={'source':key,'span':[0,len(text)]}
            cases.append({'id':f'P{i:02}','group':'public_forward','state':state,'segments':segments})
            cases.append({'id':f'R{i:02}','group':'reversed_diagnostic','state':{'before':state['after'],'after':state['before']},
                          'segments':{'before':segments['after'],'after':segments['before']},'reverse_of':f'P{i:02}'})
            cases.append({'id':f'S{i:02}','group':'synthetic_ko','state':{'before':'검토 전','after':f'검토 후{i}'},'segments':None})
            for prefix in ('P','R','S'):
                ex=('substantive' if i<=4 else 'editorial') if prefix=='P' else ('risk' if i<=4 else 'editorial') if prefix=='R' else ('risk' if i<=2 else 'editorial' if i<=4 else 'substantive')
                labels.append({'id':f'{prefix}{i:02}','expected':ex,'acceptable_labels':[ex],'rationale':'fixture'})
        corpus=root/'corpus.json';gold=root/'labels.json';corpus.write_text(json.dumps({'cases':cases,'sources':sources}));gold.write_text(json.dumps({'cases':labels}))
        self.out=root/'run';catalog={'data':[{'id':claims.runner.MODELS['jev'],'pricing':{'input':'0.000000042','output':'0'}}]}
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(catalog))),contextlib.redirect_stdout(io.StringIO()):change.prepare(self.out,corpus,gold)

    def fake_results(self, overrides=None):
        m=change.validate(self.out);cases={c['id']:c for c in m['cases']};rows=[]
        for t in m['tasks']:
            label=(overrides or {}).get(t['id'],cases[t['id']]['expected'])
            rows.append({'id':t['id'],'arm':'jev','request_sha256':t['sha256'],'status':'ok','topic':label,
                         'latency_ms':1,'reported_cost_usd':0,'list_cost_usd':0,
                         'response':{'answers':{'topic':{'type':'choice','choice':label,
                            'probabilities':{k:int(k==label) for k in change.CRITERIA}}},'usage':{'inputTokens':1}}})
        (self.out/'results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))

    def summary(self):
        with contextlib.redirect_stdout(io.StringIO()):change.report(self.out)
        return json.loads((self.out/'summary.json').read_text())

    def rewrite(self, mutate):
        p=self.out/'manifest.json';m=json.loads(p.read_text());mutate(m);raw=claims.runner.encoded(m);p.write_bytes(raw)
        (self.out/'manifest.sha256').write_text(claims.digest(raw))

    def test_scope_and_no_labels(self):
        m=change.validate(self.out);self.assertEqual(len(m['tasks']),18)
        for t in m['tasks']:self.assertEqual(set(t['body']['state']),{'before','after'})

    def test_rehashed_task_label_leak_rejected(self):
        self.rewrite(lambda m:m['tasks'][0]['body']['state'].update(expected='risk'))
        with self.assertRaisesRegex(ValueError,'Request changed'):change.validate(self.out)

    def test_rehashed_policy_change_rejected(self):
        self.rewrite(lambda m:m['decision_policy'].update(max_risk_as_editorial=2))
        with self.assertRaisesRegex(ValueError,'Contract changed'):change.validate(self.out)

    def test_source_edit_rejected(self):
        next(self.out.glob('*.source.txt')).write_text('changed')
        with self.assertRaisesRegex(ValueError,'Source changed'):change.validate(self.out)

    def test_source_span_and_reverse_pair_checked(self):
        c=json.loads((self.out/'corpus.json').read_text());l=json.loads((self.out/'labels.json').read_text());s={k:(self.out/(k+'.source.txt')).read_text() for k in c['sources']}
        c['cases'][1]['state']['before']='wrong'
        with self.assertRaisesRegex(ValueError,'span mismatch'):change.audit(c,l,s)

    def test_no_response_is_not_pass(self):
        self.assertEqual(self.summary()['decision'],'hold_no_extra_calls')

    def test_pass_is_only_candidate_not_deployment(self):
        self.fake_results();s=self.summary();self.assertEqual(s['decision'],'candidate_for_independent_real_changes_only');self.assertFalse(change.POLICY['deployment'])
        self.assertEqual(s['groups']['public_forward']['exact'],6)

    def test_one_risk_as_editorial_holds(self):
        self.fake_results({'R01':'editorial'});s=self.summary();self.assertEqual(s['decision'],'hold_no_extra_calls');self.assertEqual(s['risk_as_editorial'],['R01'])

    def test_priority_misses_and_false_alarms_hold(self):
        self.fake_results({'R01':'substantive','R02':'unresolved'});self.assertEqual(self.summary()['decision'],'hold_no_extra_calls')
        self.fake_results({'P05':'risk','P06':'substantive'});self.assertEqual(self.summary()['decision'],'hold_no_extra_calls')

    def test_criteria_extension_preserves_claim_contract_and_journal(self):
        original=claims.CRITERIA.copy()
        def check(*args):self.assertEqual(claims.runner.CRITERIA,change.CRITERIA)
        with patch.object(claims.runner,'execute',side_effect=check):claims.execute(self.out,18,False,validator=change.validate,criteria=change.CRITERIA)
        self.assertEqual(claims.CRITERIA,original)
        (self.out/'inflight.json').write_text('{}')
        with patch.object(claims.runner,'execute') as run:
            with self.assertRaisesRegex(ValueError,'Interrupted'):claims.execute(self.out,18,False,validator=change.validate,criteria=change.CRITERIA)
            run.assert_not_called()

    def test_duplicate_response_blocks_execution(self):
        self.fake_results();p=self.out/'results.jsonl';p.write_text(p.read_text()+p.read_text().splitlines()[0]+'\n')
        with patch.object(claims.runner,'execute') as run:
            with self.assertRaisesRegex(ValueError,'Duplicate'):claims.execute(self.out,18,False,validator=change.validate,criteria=change.CRITERIA)
            run.assert_not_called()


if __name__=='__main__':unittest.main()
