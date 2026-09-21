import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import route


def answer(ai=.8,dev=.2):
    return {'type':'choice','choice':'ai','probabilities':{'ai':ai,'dev':dev,'security':0,'industry':0,'other':0}}


class ProtocolTest(unittest.TestCase):
    def test_compact_classification(self):
        self.assertEqual(route.route('x',answer()),{'id':'x','status':'classified','topic':'ai','reason':'policy_pass'})

    def test_ambiguous_abstains_without_relabeling_other(self):
        self.assertEqual(route.route('x',answer(.5,.5)),{'id':'x','status':'review','topic':None,'reason':'ambiguous'})

    def test_invalid_distribution_and_choice(self):
        for a in (None,[],{},answer(float('nan'),.2),answer(.8,.8),dict(answer(),choice='unknown'),dict(answer(),choice='dev')):
            with self.subTest(a=a):self.assertEqual(route.route('x',a)['status'],'fallback')

    def test_state_allowlist_and_default_zdr(self):
        a={'body':{'state':{'title':'public','summary':'text','selected':True,'metrics':{'score':999}}}}
        body=json.loads(route.request_body(a,False))
        self.assertEqual(set(body['questions']),{'topic'})
        self.assertNotIn('selected',body['state']);self.assertNotIn('metrics',body['state'])
        self.assertTrue(body['providerOptions']['gateway']['zeroDataRetention'])
        self.assertNotIn('zeroDataRetention',json.loads(route.request_body(a,True))['providerOptions']['gateway'])

    def test_transport_failure_stops_network_and_preserves_every_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pilot=root/'pilot';pilot.mkdir();out=root/'out'
            articles=[{'id':str(i),'body':{'state':{'title':'public'}}} for i in range(10)]
            (pilot/'manifest.json').write_text(json.dumps({'articles':articles}))
            (pilot/'results.jsonl').write_text('\n'.join(json.dumps({'id':str(i),'arm':'base','status':'ok','answers':{'topic':answer()}}) for i in range(10)))
            err=urllib.error.HTTPError(route.smoke.ENDPOINT,429,'test',{},None)
            with patch.object(sys,'argv',['route.py',str(pilot),'--out',str(out),'--execute','--public-data-no-zdr']),patch.dict(os.environ,{'AI_GATEWAY_API_KEY':'offline-placeholder'}),patch.object(route.urllib.request,'build_opener') as opener,patch.object(route.time,'sleep'),contextlib.redirect_stdout(io.StringIO()):
                opener.return_value.open.side_effect=err
                self.assertEqual(route.main(),1);self.assertEqual(opener.return_value.open.call_count,1)
            records=[json.loads(x) for x in (out/'routes.jsonl').read_text().splitlines()]
            self.assertEqual(len(records),10);self.assertEqual({r['status'] for r in records},{'fallback'})
            self.assertEqual(records[0]['reason'],'request_failed');self.assertEqual(records[-1]['reason'],'batch_stopped')


if __name__=='__main__':unittest.main()
