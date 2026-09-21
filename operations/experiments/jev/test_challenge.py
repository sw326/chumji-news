import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import challenge as c


class ChallengeTests(unittest.TestCase):
    def test_input_contract_hides_expected_and_minimal_llm(self):
        case={'id':'x','expected':'security','attack_target':'dev','state':{'title':'test','summary':''}}
        j=c.body(case,'jev');l=c.body(case,'llm')
        self.assertEqual(j['state'],case['state'])
        self.assertEqual(json.loads(l['messages'][1]['content']),case['state'])
        self.assertEqual(l['max_tokens'],32)
        self.assertTrue(l['response_format']['json_schema']['strict'])
        self.assertNotIn('expected',json.dumps(j))

    def test_strict_semantic_output_validation(self):
        d={'choices':[{'finish_reason':'stop','message':{'content':'{"topic":"dev"}'}}],
           'usage':{'prompt_tokens':40,'completion_tokens':6}}
        self.assertEqual(c.parse('llm',d)[:3],('dev',40,6))
        d['choices'][0]['message']['content']='{"topic":"dev","explanation":"extra"}'
        with self.assertRaises(ValueError):c.parse('llm',d)
        probs={k:0 for k in c.CRITERIA};probs['ai']=1
        j={'answers':{'topic':{'type':'choice','choice':'dev','probabilities':probs}},'usage':{'inputTokens':40}}
        with self.assertRaises(ValueError):c.parse('jev',j)

    def test_failure_stops_and_cannot_retry(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);b=c.body({'state':{'title':'test','summary':''}},'llm')
            task={'id':'x','arm':'llm','body':b,'sha256':hashlib.sha256(c.encoded(b)).hexdigest()}
            m={'tasks':[task,{**task,'id':'y'}],'max_calls':80,'interval_seconds':0}
            raw=c.encoded(m);(out/'manifest.json').write_bytes(raw)
            (out/'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest())
            e=urllib.error.HTTPError('https://ai-gateway.vercel.sh',429,'rate limit',{},io.BytesIO(b'{"error":{"code":"rate_limited"}}'))
            with patch.dict(c.os.environ,{'AI_GATEWAY_API_KEY':'test-only'}),patch.object(c.urllib.request,'build_opener') as op:
                op.return_value.open.side_effect=e
                c.execute(out,80)
                self.assertEqual(op.return_value.open.call_count,1)
                with self.assertRaises(ValueError):c.execute(out,80)
                c.execute(out,80,continue_after_failure=True)
                self.assertEqual(op.return_value.open.call_count,2)
            rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
            self.assertEqual([r['id'] for r in rows],['x','y'])
            self.assertEqual(rows[0]['http_status'],429)


if __name__=='__main__':unittest.main()
