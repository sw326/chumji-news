#!/usr/bin/env python3
"""Public verbatim holdout for wiki#21; no production decisions or prompt changes."""
import argparse
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import random
import time
import urllib.request

import claims


def prepare(out, corpus_path, labels_path):
    corpus = json.loads(corpus_path.read_text())
    labels = json.loads(labels_path.read_text())
    by_id = {r['id']: r for r in labels['cases']}
    if len(by_id) != 30 or set(by_id) != {c['id'] for c in corpus['cases']}:
        raise ValueError('Incomplete adjudication')
    cases = []
    snapshots = {}
    for key, source in corpus['sources'].items():
        snapshots[key] = Path(source['path']).read_text()
    for case in corpus['cases']:
        if set(case['state']) != {'claim', 'evidence'}:
            raise ValueError('Unexpected state keys')
        label = by_id[case['id']]
        expected = label['expected']
        acceptable = label['acceptable_labels']
        if (expected is not None and expected not in claims.CRITERIA) or not acceptable:
            raise ValueError('Invalid label')
        if not set(acceptable) <= set(claims.CRITERIA):
            raise ValueError('Invalid ambiguity labels')
        if expected is None and len(set(acceptable)) < 2:
            raise ValueError('Ambiguous case needs alternatives')
        if expected is not None and acceptable != [expected]:
            raise ValueError('Confirmed case needs one label')
        cases.append({**case, 'expected': expected, 'group': case['slot'],
                      'acceptable_labels': acceptable, 'rationale': label['rationale']})
    cat = json.load(urllib.request.urlopen('https://ai-gateway.vercel.sh/v1/models', timeout=30))
    prices = {x['id']: x['pricing'] for x in cat['data'] if x['id'] in claims.runner.MODELS.values()}
    if set(prices) != set(claims.runner.MODELS.values()):
        raise ValueError('Missing prices')
    rng = random.Random(202609221025)
    shuffled = cases.copy()
    rng.shuffle(shuffled)
    tasks = []
    for c in shuffled:
        arms = list(claims.runner.MODELS)
        rng.shuffle(arms)
        for arm in arms:
            body = claims.request(c['state'], arm)
            tasks.append({'id': c['id'], 'arm': arm, 'body': body,
                          'sha256': claims.digest(claims.runner.encoded(body))})
    manifest = {
        'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'issue': corpus['issue'],
        'rules': claims.RULE, 'criteria': claims.CRITERIA, 'models': claims.runner.MODELS,
        'catalog_prices': prices, 'max_calls': 60, 'interval_seconds': 13,
        'observed_cost_guard_usd': .01,
        'sources': {k: {a: b for a, b in v.items() if a != 'path'} for k, v in corpus['sources'].items()},
        'cases': cases, 'tasks': tasks,
        'corpus_sha256': claims.digest(corpus_path.read_bytes()),
        'adjudication_sha256': claims.digest(labels_path.read_bytes()),
        'pilot_gate': {'min_review': 10, 'min_normal': 10, 'max_miss_rate': .1, 'max_false_rate': .1},
        'limitations': [
            'Verbatim public MDN English convenience sample, 10 correlated source clusters; not private wiki traffic.',
            'Claim/evidence from different sections of the same document; not independent world-truth verification.',
            'Two AI pre-call reviewers, not human gold. Ambiguous labels excluded from primary error rates.',
            'Fixed excerpt selection can omit relevant evidence; a review flag is not proof of a false claim.',
            'No measured human review-time saving, model calibration, stable version pin or cache control.',
        ],
    }
    out.mkdir(parents=True, exist_ok=False)
    for key, snapshot in snapshots.items():
        (out / (key + '.source.txt')).write_text(snapshot)
    (out / 'corpus-before-calls.json').write_bytes(corpus_path.read_bytes())
    (out / 'labels-before-calls.json').write_bytes(labels_path.read_bytes())
    raw = claims.runner.encoded(manifest)
    (out / 'manifest.json').write_bytes(raw)
    (out / 'manifest.sha256').write_text(claims.digest(raw))
    validate(out)
    print(json.dumps({'sha256': claims.digest(raw), 'cases': len(cases), 'tasks': len(tasks),
                      'labels': dict(Counter(c['expected'] or 'ambiguous' for c in cases))}))


def validate(out):
    m = claims.validate(out)
    for name, key in [('corpus-before-calls.json', 'corpus_sha256'),
                      ('labels-before-calls.json', 'adjudication_sha256')]:
        if claims.digest((out / name).read_bytes()) != m[key]:
            raise ValueError('Pre-call record changed')
    corpus = json.loads((out / 'corpus-before-calls.json').read_text())
    labels = json.loads((out / 'labels-before-calls.json').read_text())
    original = {c['id']: c for c in corpus['cases']}
    by_id = {c['id']: c for c in labels['cases']}
    if (len(original) != 30 or len(by_id) != 30 or
            set(original) != {c['id'] for c in m['cases']} or set(original) != set(by_id)):
        raise ValueError('Pre-call case set changed')
    for c in m['cases']:
        if set(c['state']) != {'claim', 'evidence'}:
            raise ValueError('Unexpected state keys')
        if any(c.get(k) != v for k, v in original[c['id']].items()):
            raise ValueError('Case differs from pre-call corpus')
        if any(c.get(k) != by_id[c['id']][k] for k in ('expected', 'acceptable_labels', 'rationale')):
            raise ValueError('Label differs from pre-call adjudication')
        source = (out / (c['source'] + '.source.txt')).read_text()
        a, b = c['claim_span']
        if c['state']['claim'] != c['claim_context'] + '\n\n' + source[a:b]:
            raise ValueError('Claim not verbatim')
        for x, y in m['sources'][c['source']]['spans']:
            if a < y and x < b:
                raise ValueError('Claim overlaps evidence')
    return m


def report(out):
    m = validate(out)
    # Reuse latency, costs, routing, response parsing, and full-case listing.
    # Replace phase-one's fixed 10/20 author-label gate and grouping completely.
    with contextlib.redirect_stdout(io.StringIO()):
        claims.report(out)
    s = json.loads((out / 'summary.json').read_text())
    cases = {c['id']: c for c in m['cases']}
    rows = claims.read_results(out, m)
    for arm, metrics in s['arms'].items():
        ok = [r for r in rows if r['arm'] == arm and r['status'] == 'ok']
        certain = [r for r in ok if cases[r['id']]['expected'] is not None]
        normal = [r for r in certain if cases[r['id']]['expected'] == 'supported']
        need = [r for r in certain if cases[r['id']]['expected'] != 'supported']
        miss = [r['id'] for r in need if r['topic'] == 'supported']
        false = [r['id'] for r in normal if r['topic'] != 'supported']
        ambiguous = [r for r in ok if cases[r['id']]['expected'] is None]
        metrics.update(
            exact=sum(r['topic'] == cases[r['id']]['expected'] for r in certain),
            exact_denominator=len(certain), review_required_valid=len(need), normal_valid=len(normal),
            missed_review_ids=miss, false_alarm_ids=false,
            confusion=dict(Counter(cases[r['id']]['expected'] + ' -> ' + r['topic'] for r in certain)),
            ambiguous_valid=len(ambiguous),
            ambiguous_outside_acceptable=[r['id'] for r in ambiguous
                                          if r['topic'] not in cases[r['id']]['acceptable_labels']],
        )
        metrics['groups'] = {g: {
            'valid_certain': sum(cases[r['id']]['slot'] == g for r in certain),
            'exact': sum(cases[r['id']]['slot'] == g and cases[r['id']]['expected'] == r['topic'] for r in certain)
        } for g in ('intro', 'return', 'parameter')}
        metrics['pilot_gate'] = ('incomplete' if len(ok) != 30 else
                                 'insufficient' if len(need) < 10 or len(normal) < 10 else
                                 'met' if len(miss) / len(need) <= .1 and len(false) / len(normal) <= .1 else 'not_met')
    s['mismatches'] = [r for r in s['mismatches'] if r['expected'] is not None]
    s['precall_label_counts'] = dict(Counter(c['expected'] or 'ambiguous' for c in m['cases']))
    for row in s['all_cases']:
        row['acceptable_labels'] = cases[row['id']]['acceptable_labels']
        row['rationale'] = cases[row['id']]['rationale']
    s['decision'] = 'Evaluate observation follow-up only; no production integration or automatic approval.'
    (out / 'summary.json').write_text(json.dumps(s, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in s.items() if k not in ('all_cases', 'mismatches')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'execute', 'report'])
    p.add_argument('out', type=Path)
    p.add_argument('--corpus', type=Path)
    p.add_argument('--labels', type=Path)
    p.add_argument('--limit', type=int, default=60)
    p.add_argument('--public-data-no-zdr', action='store_true')
    p.add_argument('--continue-after-failure', action='store_true')
    a = p.parse_args()
    if a.action == 'prepare':
        prepare(a.out, a.corpus, a.labels)
    elif a.action == 'execute':
        if not a.public_data_no_zdr:
            p.error('Explicit public-only no-ZDR acknowledgement required')
        validate(a.out)
        claims.execute(a.out, a.limit, a.continue_after_failure)
    else:
        report(a.out)
