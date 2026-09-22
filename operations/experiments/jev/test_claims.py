import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import claims


class ClaimsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.out=Path(self.tmp.name)/'trial'
        s='Public test excerpt.'
        sources={k:{'snapshot_text':s,'snapshot_sha256':claims.digest(s.encode()),
                    'spans':[[0,len(s)]],'excerpt':s,'url':'https://example.org/public',
                    'fetchedAt':'2026-09-22T01:00:00Z'} for k in claims.FIXTURES}
        cat={'data':[{'id':id,'pricing':{'input':'0.0000001','output':'0.0000004'}}
                     for id in claims.runner.MODELS.values()]}
        with patch('urllib.request.urlopen',return_value=io.StringIO(json.dumps(cat))),contextlib.redirect_stdout(io.StringIO()):
            claims.prepare(self.out,sources)

    def test_scope_and_label_exclusion(self):
        m=claims.validate(self.out)
        self.assertEqual(len(m['tasks']),60)
        self.assertEqual(sum(c['expected']=='supported' for c in m['cases']),10)
        for t in m['tasks']:
            state=t['body'].get('state') or json.loads(t['body']['messages'][1]['content'])
            self.assertEqual(set(state),{'claim','evidence'})

    def test_changed_manifest_rejected(self):
        with (self.out/'manifest.json').open('a') as f:f.write(' ')
        with self.assertRaisesRegex(ValueError,'Manifest changed'):claims.validate(self.out)

    def test_changed_source_rejected(self):
        (self.out/'sort.source.txt').write_text('Changed')
        with self.assertRaisesRegex(ValueError,'Source changed'):claims.validate(self.out)

    def test_duplicate_attempt_rejected(self):
        m=claims.validate(self.out);t=m['tasks'][0]
        r={'id':t['id'],'arm':t['arm'],'request_sha256':t['sha256'],'status':'error'}
        (self.out/'results.jsonl').write_text((json.dumps(r)+'\n')*2)
        with self.assertRaisesRegex(ValueError,'Duplicate'):claims.read_results(self.out,m)

    def test_interrupted_run_blocks_network(self):
        (self.out/'inflight.json').write_text('{}')
        with patch.object(claims.runner,'execute') as run:
            with self.assertRaisesRegex(ValueError,'Interrupted'):claims.execute(self.out,60,False)
            run.assert_not_called()

    def test_failure_requires_explicit_continuation(self):
        m=claims.validate(self.out);t=m['tasks'][0]
        r={'id':t['id'],'arm':t['arm'],'request_sha256':t['sha256'],'status':'error'}
        (self.out/'results.jsonl').write_text(json.dumps(r)+'\n')
        with patch.object(claims.runner,'execute') as run:
            with self.assertRaisesRegex(ValueError,'Prior failure'):claims.execute(self.out,60,False)
            run.assert_not_called()
            claims.execute(self.out,59,True)
            run.assert_called_once_with(self.out,59,True)

    def test_unattempted_is_not_pass(self):
        with contextlib.redirect_stdout(io.StringIO()):claims.report(self.out)
        s=json.loads((self.out/'summary.json').read_text())
        for arm in s['arms'].values():
            self.assertEqual(arm['pilot_gate'],'incomplete')
            self.assertEqual(arm['unresolved_api_or_unattempted'],30)

if __name__=='__main__':unittest.main()
