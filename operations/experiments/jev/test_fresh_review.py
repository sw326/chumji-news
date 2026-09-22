import unittest
import fresh_review as f


def fixture():
    cases=[]
    for i in range(1,5):
        state={'before': 'old', 'after': 'new'}
        c={'id':f'N{i:02}', 'commit':str(i), 'parent':'parent',
           'file':'files/en-us/web/test/index.md', 'state':state, 'sources':{}}
        for v,sha in [('before','parent'),('after',str(i))]:
            c['sources'][v]={'url':f'https://raw.githubusercontent.com/mdn/content/{sha}/{c["file"]}',
                             'sha256':f.claims.digest(state[v].encode())}
        cases.append(c)
    return cases


class FreshReviewTests(unittest.TestCase):
    def test_valid_public_pairs(self): f.audit(fixture())

    def test_missing_duplicate_or_excess_batch_refused(self):
        c=fixture()
        for bad in (c[:3], c+[c[0]], c*3):
            with self.assertRaises(ValueError): f.audit(bad)

    def test_url_or_snapshot_tampering_refused(self):
        for field,value in [('url','https://example.org/private'),('sha256','bad')]:
            c=fixture(); c[0]['sources']['before'][field]=value
            with self.assertRaises(ValueError): f.audit(c)

    def test_label_in_state_refused(self):
        c=fixture(); c[0]['state']['expected']='risk'
        with self.assertRaises(ValueError): f.audit(c)

    def test_oversize_refused_even_with_updated_hash(self):
        c=fixture(); c[0]['state']['after']='x'*16000
        c[0]['sources']['after']['sha256']=f.claims.digest(c[0]['state']['after'].encode())
        with self.assertRaisesRegex(ValueError, 'large'): f.audit(c)


if __name__ == '__main__': unittest.main()
