#!/usr/bin/env python3
"""Wiki#22: six fixed claims, append-only evidence, unchanged Jev question."""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import statistics
import time
import urllib.request

import claims

PAIR_IDS = {'H01', 'H07', 'H15', 'H17', 'H20', 'H24'}
VARIANTS = {'baseline', 'enriched'}
EXPECTED_PRIOR_SHA = '128dee0894a498e52e659016c38b3409082f9a10b2fc1c5db806af489c7e9b41'
DECISION_POLICY = {
    'critical_case': 'H15-enriched',
    'critical_supported': 'stop_this_wiki_claim_checker_adoption_experiment',
    'incomplete_or_nonconflict_or_ambiguous_or_unmet_pair': 'hold_no_extra_calls',
    'all_pairs_acceptable_and_critical_conflict': 'review_preparation_cost_and_transitions_before_any_followup',
    'deployment_authorized': False,
}


def audit(corpus, labels, prior, snapshots):
    cases = corpus['cases']
    ids = {f'{p}-{v}' for p in PAIR_IDS for v in VARIANTS}
    if len(cases) != 12 or {c['id'] for c in cases} != ids:
        raise ValueError('Scope must be six fixed pairs')
    gold = {x['id']: x for x in labels['cases']}
    if len(labels['cases']) != 12 or set(gold) != ids:
        raise ValueError('Incomplete labels')
    old = {c['id']: c for c in prior['cases']}
    by_id = {c['id']: c for c in cases}
    for key, source in corpus['sources'].items():
        if claims.digest(snapshots[key].encode()) != source['snapshot_sha256']:
            raise ValueError('Source changed')
    for c in cases:
        if (c['pair_id'] not in PAIR_IDS or c['variant'] not in VARIANTS or
                c['id'] != c['pair_id'] + '-' + c['variant']):
            raise ValueError('Invalid pair identity')
        if set(c['state']) != {'claim', 'evidence'}:
            raise ValueError('Unexpected state keys')
        oc = old[c['pair_id']]
        if (c['state']['claim'] != oc['state']['claim'] or c['claim_source'] != oc['source'] or
                c['claim_span'] != oc['claim_span'] or c['claim_context'] != oc['claim_context']):
            raise ValueError('Claim differs from frozen prior')
        pieces = []
        for seg in c['segments']:
            a, b = seg['span']
            snapshot = snapshots[seg['source']]
            if not 0 <= a < b <= len(snapshot):
                raise ValueError('Invalid evidence span')
            if seg['source'] == c['claim_source']:
                x, y = c['claim_span']
                if a < y and x < b:
                    raise ValueError('Claim copied into evidence')
            pieces.append(snapshot[a:b])
        if '\n\n'.join(pieces) != c['state']['evidence']:
            raise ValueError('Evidence span mismatch')
        if c['variant'] == 'baseline':
            if c['state'] != oc['state']:
                raise ValueError('Baseline changed')
            if (gold[c['id']]['expected'] != oc['expected'] or
                    gold[c['id']]['acceptable_labels'] != oc['acceptable_labels']):
                raise ValueError('Historic baseline label changed')
        else:
            base = by_id[c['pair_id'] + '-baseline']
            if (c['segments'][:len(base['segments'])] != base['segments'] or
                    len(c['segments']) <= len(base['segments']) or
                    not c['state']['evidence'].startswith(base['state']['evidence'] + '\n\n')):
                raise ValueError('Enrichment must be append-only')
            body = c['state']['claim'][len(c['claim_context']) + 2:]
            if body in c['state']['evidence']:
                raise ValueError('Claim copied into evidence')
        label = gold[c['id']]
        allowed = label['acceptable_labels']
        if not allowed or not set(allowed) <= set(claims.CRITERIA):
            raise ValueError('Invalid acceptable labels')
        if label['expected'] is None:
            if len(set(allowed)) < 2:
                raise ValueError('Ambiguity needs alternatives')
        elif allowed != [label['expected']] or label['expected'] not in claims.CRITERIA:
            raise ValueError('Invalid confirmed label')


def prepare(out, corpus_path, labels_path):
    corpus = json.loads(corpus_path.read_text())
    labels = json.loads(labels_path.read_text())
    prior_raw = Path(corpus['prior_manifest_path']).read_bytes()
    if claims.digest(prior_raw) != EXPECTED_PRIOR_SHA or corpus['prior_manifest_sha256'] != EXPECTED_PRIOR_SHA:
        raise ValueError('Prior manifest changed')
    prior = json.loads(prior_raw)
    snapshots = {k: Path(s['path']).read_text() for k, s in corpus['sources'].items()}
    audit(corpus, labels, prior, snapshots)
    catalog = json.load(urllib.request.urlopen('https://ai-gateway.vercel.sh/v1/models', timeout=30))
    model = claims.runner.MODELS['jev']
    prices = {x['id']: x['pricing'] for x in catalog['data'] if x['id'] == model}
    if model not in prices:
        raise ValueError('Missing Jev price')
    gold = {c['id']: c for c in labels['cases']}
    cases = [{**c, **{k: gold[c['id']][k] for k in ('expected', 'acceptable_labels', 'rationale')}}
             for c in corpus['cases']]
    shuffled = cases.copy()
    random.Random(202609221107).shuffle(shuffled)
    tasks = []
    for c in shuffled:
        body = claims.request(c['state'], 'jev')
        tasks.append({'id': c['id'], 'arm': 'jev', 'body': body,
                      'sha256': claims.digest(claims.runner.encoded(body))})
    manifest = {'issue': corpus['issue'], 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'rules': claims.RULE, 'criteria': claims.CRITERIA, 'models': {'jev': model},
                'catalog_prices': prices, 'max_calls': 12, 'interval_seconds': 3.2,
                'observed_cost_guard_usd': .01, 'cases': cases, 'tasks': tasks,
                'decision_policy': DECISION_POLICY,
                'sources': {k: {a: b for a, b in v.items() if a != 'path'} for k, v in corpus['sources'].items()},
                'corpus_sha256': claims.digest(corpus_path.read_bytes()),
                'labels_sha256': claims.digest(labels_path.read_bytes()),
                'prior_sha256': EXPECTED_PRIOR_SHA}
    out.mkdir(parents=True, exist_ok=False)
    for key, text in snapshots.items():
        (out / (key + '.source.txt')).write_text(text)
    for name, data in [('corpus.json', corpus_path.read_bytes()), ('labels.json', labels_path.read_bytes()),
                       ('prior-manifest.json', prior_raw)]:
        (out / name).write_bytes(data)
    raw = claims.runner.encoded(manifest)
    (out / 'manifest.json').write_bytes(raw)
    (out / 'manifest.sha256').write_text(claims.digest(raw))
    validate(out)
    print(json.dumps({'manifest_sha256': claims.digest(raw), 'cases': 12, 'max_calls': 12}))


def validate(out):
    raw = (out / 'manifest.json').read_bytes()
    if claims.digest(raw) != (out / 'manifest.sha256').read_text():
        raise ValueError('Manifest changed')
    m = json.loads(raw)
    if (m['rules'] != claims.RULE or m['criteria'] != claims.CRITERIA or
            m['models'] != {'jev': claims.runner.MODELS['jev']} or
            m['max_calls'] != 12 or m['interval_seconds'] < 3.2 or
            m['decision_policy'] != DECISION_POLICY):
        raise ValueError('Contract changed')
    for name, key in [('corpus.json', 'corpus_sha256'), ('labels.json', 'labels_sha256'),
                      ('prior-manifest.json', 'prior_sha256')]:
        if claims.digest((out / name).read_bytes()) != m[key]:
            raise ValueError('Frozen record changed')
    if m['prior_sha256'] != EXPECTED_PRIOR_SHA:
        raise ValueError('Prior manifest changed')
    corpus = json.loads((out / 'corpus.json').read_text())
    labels = json.loads((out / 'labels.json').read_text())
    prior = json.loads((out / 'prior-manifest.json').read_text())
    snapshots = {k: (out / (k + '.source.txt')).read_text() for k in corpus['sources']}
    audit(corpus, labels, prior, snapshots)
    gold = {c['id']: c for c in labels['cases']}
    expected = [{**c, **{k: gold[c['id']][k] for k in ('expected', 'acceptable_labels', 'rationale')}}
                for c in corpus['cases']]
    if m['cases'] != expected:
        raise ValueError('Case or label differs from frozen record')
    cases = {c['id']: c for c in m['cases']}
    if len(m['tasks']) != 12 or {(t['id'], t['arm']) for t in m['tasks']} != {(i, 'jev') for i in cases}:
        raise ValueError('Invalid task set')
    for t in m['tasks']:
        body = claims.request(cases[t['id']]['state'], 'jev')
        encoded = claims.runner.encoded(body)
        if t['body'] != body or t['sha256'] != claims.digest(encoded) or len(encoded) > 16000:
            raise ValueError('Request changed')
    return m


def report(out):
    m = validate(out)
    rows = claims.read_results(out, m)
    ok = {r['id']: r for r in rows if r['status'] == 'ok'}
    cases = {c['id']: c for c in m['cases']}
    pairs = []
    for id in sorted(PAIR_IDS):
        pair = {'id': id}
        for variant in sorted(VARIANTS):
            key = id + '-' + variant
            c = cases[key]
            got = ok.get(key, {}).get('topic')
            pair[variant] = {'expected': c['expected'], 'acceptable_labels': c['acceptable_labels'],
                             'got': got, 'in_acceptable': got in c['acceptable_labels'] if got else None,
                             'evidence_chars': len(c['state']['evidence'])}
        pairs.append(pair)
    enriched_conflict = ok.get('H15-enriched', {}).get('topic')
    if enriched_conflict == 'supported':
        decision = 'stop_this_wiki_claim_checker_adoption_experiment'
    elif (len(ok) != 12 or enriched_conflict != 'conflict' or
          any(p['enriched']['expected'] is None or not p['enriched']['in_acceptable'] or
              not p['baseline']['in_acceptable'] for p in pairs)):
        decision = 'hold_no_extra_calls'
    else:
        decision = 'review_preparation_cost_and_transitions_before_any_followup'
    summary = {'manifest_sha256': claims.digest((out / 'manifest.json').read_bytes()),
               'attempted': len(rows), 'valid': len(ok), 'unresolved_api_or_unattempted': 12-len(ok),
               'pairs': pairs, 'decision': decision,
               'median_ms': statistics.median(r['latency_ms'] for r in ok.values()) if ok else None,
               'list_cost_usd': sum(r['list_cost_usd'] for r in ok.values()),
               'reported_cost_known_n': sum(r['reported_cost_usd'] is not None for r in ok.values()),
               'reported_cost_usd': sum(r['reported_cost_usd'] or 0 for r in ok.values()),
               'label_counts': dict(Counter(r['topic'] for r in ok.values()))}
    runs = out / 'runs.jsonl'
    summary['segment_wall_seconds'] = sum(json.loads(x)['wall_seconds'] for x in runs.read_text().splitlines()) if runs.exists() else 0
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'execute', 'report'])
    p.add_argument('out', type=Path)
    p.add_argument('--corpus', type=Path)
    p.add_argument('--labels', type=Path)
    p.add_argument('--limit', type=int, default=12)
    p.add_argument('--public-data-no-zdr', action='store_true')
    p.add_argument('--continue-after-failure', action='store_true')
    a = p.parse_args()
    if a.action == 'prepare':
        prepare(a.out, a.corpus, a.labels)
    elif a.action == 'execute':
        if not a.public_data_no_zdr:
            p.error('Public-only no-ZDR acknowledgement required')
        claims.execute(a.out, a.limit, a.continue_after_failure, validator=validate)
    else:
        report(a.out)
