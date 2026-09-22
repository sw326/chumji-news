import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import actions as a
import resume as r
import sequential as s


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/'source'
        self.dest = Path(self.tmp.name)/'copy'
        self.source.mkdir()
        (self.source/'controller.lock').touch()
        (self.source/'fixture.json').write_text('{}')
        (self.source/'search-round-1').mkdir()
        (self.source/'search-round-1/results.jsonl').write_text('{"status":"error"}\n')
        self.frozen_failures = [['search-round-1','frozen-error-hash']]
        for name, value in [('load_fixture',{}), ('validate_batch',{'criteria':[]})]:
            mock = patch.object(a, name, return_value=value)
            mock.start(); self.addCleanup(mock.stop)
        mock = patch.object(r, 'failures', return_value=self.frozen_failures)
        self.failure_mock = mock.start(); self.addCleanup(mock.stop)

    def prepare(self):
        with patch('builtins.print'): r.prepare(self.source,self.dest)

    def test_exclusive_copy_original_and_old_prefix_preserved(self):
        before=r.inventory(self.source); self.prepare()
        ledger=self.dest/'search-round-1/results.jsonl'
        with ledger.open('a') as f: f.write('{"status":"ok"}\n')
        r.verify(self.dest)
        self.assertEqual(before,r.inventory(self.source))
        with self.assertRaises(FileExistsError): self.prepare()
        ledger.write_text('{"status":"ok"}\n')
        with self.assertRaisesRegex(ValueError,'Historical ledger'): r.verify(self.dest)

    def test_unknown_inflight_blocks_before_copy(self):
        (self.source/'search-round-1/inflight.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'inflight'): self.prepare()
        self.assertFalse(self.dest.exists())

    def test_new_failure_blocks_even_after_previous_error_whitelisted(self):
        self.prepare()
        self.failure_mock.return_value=self.frozen_failures+[['search-round-1','new-error']]
        with self.assertRaisesRegex(ValueError,'New or altered failure'): r.verify(self.dest)

    def test_source_input_or_plan_tamper_blocks(self):
        self.prepare()
        (self.dest/'fixture.json').write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError,'Frozen input'): r.verify(self.dest)
        (self.dest/'fixture.json').write_text('{}')
        (self.source/'fixture.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'Original evidence'): r.verify(self.dest)

    def test_plan_hash_tamper_blocks(self):
        self.prepare()
        (self.dest/'continuation.sha256').write_text('changed')
        with self.assertRaisesRegex(ValueError,'plan changed'): r.verify(self.dest)

    def test_default_strict_runner_still_rejects_old_error(self):
        with patch.object(s,'all_rows',return_value=[{'status':'error'}]):
            with self.assertRaisesRegex(ValueError,'Prior failure'):
                s.execute_batch(self.source,self.source/'search-round-1')

    def test_runner_transport_skips_success_and_failure(self):
        # Exercise real transport loop; only the third task may reach the opener.
        runner=a.claims.runner
        out=self.source/'transport';out.mkdir()
        tasks=[{'id':x,'arm':'jev','body':{'x':x},'sha256':a.hash_obj({'x':x})} for x in ['old-ok','old-error','new','later']]
        manifest={'interval_seconds':3.2,'max_calls':4,'tasks':tasks,'catalog_prices':{runner.MODELS['jev']:{'input':'0','output':'0'}}}
        raw=runner.encoded(manifest)
        (out/'manifest.json').write_bytes(raw)
        (out/'manifest.sha256').write_text(a.claims.digest(raw))
        old=[{'id':'old-ok','arm':'jev','status':'ok'},{'id':'old-error','arm':'jev','status':'error'}]
        (out/'results.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in old))
        with patch.dict('os.environ',{'AI_GATEWAY_API_KEY':'offline-test-only'}), patch.object(runner.urllib.request,'build_opener') as opener, patch.object(runner.time,'sleep'), patch('builtins.print'):
            opener.return_value.open.side_effect=TimeoutError('offline')
            runner.execute(out,4,True)
            self.assertEqual(opener.return_value.open.call_count,1)
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(req.data),{'x':'new'})
        rows=[json.loads(x) for x in (out/'results.jsonl').read_text().splitlines()]
        self.assertEqual(rows[:2],old)
        self.assertEqual(rows[-1]['status'],'error')


if __name__=='__main__': unittest.main()
