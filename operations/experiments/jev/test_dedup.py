import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import dedup

class DedupTest(unittest.TestCase):
    def test_no_label_leak_and_direction(self):
        state={'A':{'title':'old','summary':'a'},'B':{'title':'new','summary':'b'}}
        b=dedup.body(state)
        self.assertEqual(b['state'],state)
        self.assertEqual(set(b),{'model','state','questions','providerOptions'})
        self.assertNotIn('expected',json.dumps(b))
        self.assertNotEqual(b,dedup.body({'A':state['B'],'B':state['A']}))
    def test_no_drop_and_missing_summary(self):
        state={'A':{'summary':'a'},'B':{'summary':''}}
        probs={'duplicate':1.,'followup':0.,'distinct':0.,'unknown':0.}
        self.assertEqual(dedup.action(state,'duplicate',probs),'review_missing_summary')
        self.assertEqual(dedup.action(state,'followup',probs),'keep_or_review')
        state['B']['summary']='b'
        self.assertEqual(dedup.action(state,'duplicate',probs),'duplicate_candidate_only')
    def test_invalid_probabilities(self):
        for p in [{'duplicate':1.},dict.fromkeys(dedup.CRITERIA,.9),dict.fromkeys(dedup.CRITERIA,float('nan'))]:
            with self.assertRaises(ValueError):dedup.parse({'answers':{'relation':{'type':'choice','choice':'duplicate','probabilities':p}}})
    def test_failure_stops_and_reexecution_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.json'
            source.write_text(json.dumps([{'title':'public','summary':'','article_url':'https://example.com/'+str(i)} for i in range(300)]))
            out=root/'out';dedup.prepare(out,source)
            with patch.dict('os.environ',{'AI_GATEWAY_API_KEY':'test-sentinel'}),patch('urllib.request.build_opener') as op:
                op.return_value.open.side_effect=TimeoutError()
                dedup.execute(out)
                self.assertEqual(op.return_value.open.call_count,1)
                self.assertEqual(len((out/'results.jsonl').read_text().splitlines()),1)
                with self.assertRaises(FileExistsError):dedup.execute(out)
                self.assertEqual(op.return_value.open.call_count,1)

if __name__=='__main__':unittest.main()
