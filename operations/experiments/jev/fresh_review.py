#!/usr/bin/env python3
"""#26: bounded new public batch, unchanged classifier, independent agent reviews."""
import argparse
import json
from pathlib import Path
import sys
import urllib.request

import change_review as cr
import claims

ISSUE = 'https://github.com/sw326/chumji-wiki/issues/26'


def audit(cases):
    n = len(cases)
    if not 4 <= n <= 8 or {c['id'] for c in cases} != {f'N{i:02}' for i in range(1, n+1)}:
        raise ValueError('Batch size or IDs invalid')
    if len({c['commit'] for c in cases}) != n:
        raise ValueError('Duplicate commit')
    for c in cases:
        if set(c['state']) != {'before', 'after'} or c['state']['before'] == c['state']['after']:
            raise ValueError('Invalid pair')
        if not c['file'].startswith('files/en-us/') or not c['file'].endswith('/index.md') or c['parent'] == c['commit']:
            raise ValueError('Invalid public source')
        for variant, sha in [('before', c['parent']), ('after', c['commit'])]:
            source = c['sources'][variant]
            if (source['url'] != f"https://raw.githubusercontent.com/mdn/content/{sha}/{c['file']}"
                    or claims.digest(c['state'][variant].encode()) != source['sha256']):
                raise ValueError('Public snapshot mismatch')
        if len(claims.runner.encoded(cr.request(c['state']))) > 16000:
            raise ValueError('Request too large')


def validate(out):
    raw = (out/'manifest.json').read_bytes()
    if claims.digest(raw) != (out/'manifest.sha256').read_text():
        raise ValueError('Manifest changed')
    m = json.loads(raw)
    corpus = (out/'corpus.json').read_bytes()
    if claims.digest(corpus) != m['corpus_sha256'] or json.loads(corpus)['cases'] != m['cases']:
        raise ValueError('Frozen corpus changed')
    audit(m['cases'])
    if (m['issue'] != ISSUE or m['rules'] != cr.RULE or m['criteria'] != cr.CRITERIA
            or m['max_calls'] != len(m['cases']) or m['interval_seconds'] != 3.2
            or m['observed_cost_guard_usd'] != .01 or m['models'] != {'jev': claims.runner.MODELS['jev']}):
        raise ValueError('Contract changed')
    expected = []
    for c in sorted(m['cases'], key=lambda c: (c['committed_at'], c['id'])):
        body = cr.request(c['state'])
        expected.append({'id': c['id'], 'arm': 'jev', 'body': body,
                         'sha256': claims.digest(claims.runner.encoded(body))})
    if expected != m['tasks']:
        raise ValueError('Tasks changed')
    return m


def prepare(prep, out):
    raw = (prep/'corpus.json').read_bytes()
    cases = json.loads(raw)['cases']
    audit(cases)
    # Catalog contains public prices only; API execution is separate and protected.
    catalog = json.load(urllib.request.urlopen('https://ai-gateway.vercel.sh/v1/models', timeout=30))
    model = claims.runner.MODELS['jev']
    prices = {r['id']: r['pricing'] for r in catalog['data'] if r['id'] == model}
    if model not in prices:
        raise ValueError('Missing price')
    tasks = []
    for c in sorted(cases, key=lambda c: (c['committed_at'], c['id'])):
        body = cr.request(c['state'])
        tasks.append({'id': c['id'], 'arm': 'jev', 'body': body,
                      'sha256': claims.digest(claims.runner.encoded(body))})
    manifest = {'issue': ISSUE, 'rules': cr.RULE, 'criteria': cr.CRITERIA,
                'cases': cases, 'tasks': tasks, 'corpus_sha256': claims.digest(raw),
                'models': {'jev': model}, 'catalog_prices': prices, 'max_calls': len(cases),
                'interval_seconds': 3.2, 'observed_cost_guard_usd': .01}
    out.mkdir(parents=True, exist_ok=False)
    (out/'corpus.json').write_bytes(raw)
    wire = claims.runner.encoded(manifest)
    (out/'manifest.json').write_bytes(wire)
    (out/'manifest.sha256').write_text(claims.digest(wire))
    validate(out)
    return claims.digest(wire)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'validate', 'execute'])
    p.add_argument('out', type=Path)
    p.add_argument('--prep', type=Path)
    p.add_argument('--public-data-no-zdr', action='store_true')
    a = p.parse_args()
    if a.action == 'prepare': print(prepare(a.prep, a.out))
    elif a.action == 'validate': print(len(validate(a.out)['cases']))
    else:
        if not a.public_data_no_zdr: p.error('Public-only no-ZDR acknowledgement required')
        if sys.version_info[:2] != (3, 11):
            p.error('Use the documented protected-proxy interpreter /opt/homebrew/bin/python3.11; do not disable TLS')
        m = validate(a.out)
        claims.execute(a.out, m['max_calls'], False, validator=validate, criteria=cr.CRITERIA)
