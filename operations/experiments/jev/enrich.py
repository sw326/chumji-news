#!/usr/bin/env python3
"""Freeze verbatim excerpts and paired sparse/enriched news diagnostics. No publishing."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import statistics
import dedup
from challenge import encoded

# Paragraph positions refer to the saved 2026-09-21 web-fetch snapshots.
# No generated summaries. Selection is manual and NOT an independent blind gold set.
PARAGRAPHS = {
    'R01A': [6, 7, 9, 10, 11], 'R01B': [11],
    'R02A': [5], 'R02B': [9, 10, 11, 30],
    'R03A': [3, 4], 'R03B': [8, 17, 18, 25],
    'R04A': [5, 6],
    'R05A': [5], 'R05B': [9, 13],
    'R06A': [15, 16, 17, 18],
    'R07A': [14, 16, 17], 'R07B': [14, 16, 17],
    'R08A': [47, 48], 'R08B': [5, 6],
}
EXPECTED = {
    'R01': ('duplicate', 'B is the short wire; A already includes its event plus statements.'),
    'R02': ('duplicate', 'Selected migration, expiry and renewal facts are a translation of the linked source.'),
    'R03': ('distinct', 'Independent co-op opinion, explicitly not an announcement by the owner.'),
    'R04': ('followup', 'B adds an availability restriction: not yet Bedrock, Vertex or Foundry.'),
    'R05': ('duplicate', 'Selected launch/provenance/privacy facts restate the linked Apple source.'),
    'R06': ('distinct', 'Independent 2048 evaluation is not the model launch announcement.'),
    'R07': ('distinct', 'Separate recurring week and weekend discussions, with different dates.'),
    'R08': ('distinct', 'LLM opinion versus passkey opinion: unrelated subjects.'),
}

def excerpt(source):
    key, text = source['id'], source['text']
    if source['status'] != 200:
        raise ValueError('Source unavailable: ' + key)
    if key == 'R04B':
        start = text.index('  * Added AGENTS.md support:')
        spans = [(start, text.index('\n', start))]
    elif key == 'R06B':
        spans = [(text.index('I finally got a chance'), text.index('\n\n## scores'))]
    else:
        paragraphs = text.split('\n\n')
        starts = []; offset = 0
        for p in paragraphs:
            starts.append(offset); offset += len(p) + 2
        spans = [(starts[i], starts[i] + len(paragraphs[i])) for i in PARAGRAPHS[key]]
    selected = [text[a:b] for a, b in spans]
    if any(not p.strip() or '<<<' in p or 'SECURITY NOTICE' in p for p in selected):
        raise ValueError('Invalid selected span')
    return {'text': '\n\n'.join(selected), 'spans': spans,
            'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'url': source['url'], 'fetched_at': source['fetchedAt'],
            'fetch_truncated': source.get('truncated', False)}

def prepare(out, sources_path, prior_path):
    source_raw = sources_path.read_bytes()
    sources = {s['id']: s for s in json.loads(source_raw)}
    excerpts = {key: excerpt(value) for key, value in sources.items()}
    prior = json.loads(prior_path.read_bytes())
    cases = []; enriched = {}
    for old in prior['cases']:
        if old['group'] != 'public':
            continue
        key = old['id']; state = copy.deepcopy(old['state'])
        for side in ('A', 'B'):
            state[side]['summary'] = excerpts[key + side]['text']
        enriched[key] = state
        arms = ['sparse', 'enriched']
        random.Random(key).shuffle(arms)
        for arm in arms:
            label, reason = EXPECTED[key]
            cases.append({'id': key + '_' + arm, 'pair': key, 'group': arm,
                          'expected': label if arm == 'enriched' else None,
                          'rationale': reason if arm == 'enriched' else 'Sparse input has different evidence; no full-text gold imposed.',
                          'state': old['state'] if arm == 'sparse' else state})
    # Text containment, NOT a reconstruction of historical publication order.
    s = enriched['R01']
    cases.append({'id': 'R01_reverse', 'pair': 'R01', 'group': 'reverse',
                  'expected': 'followup', 'rationale': 'Long wire adds Google/Irregular statements absent from short wire.',
                  'state': {'A': s['B'], 'B': s['A']}})
    for c in cases:
        c['body'] = dedup.body(c['state'])
        c['request_sha256'] = hashlib.sha256(encoded(c['body'])).hexdigest()
        if len(encoded(c['body'])) > 16000:
            raise ValueError('Request too large: ' + c['id'])
    assert len(cases) == 17
    m = {'cases': cases, 'excerpts': excerpts, 'max_calls': 17,
         'rules': dedup.RULE, 'criteria': dedup.CRITERIA,
         'source_sha256': hashlib.sha256(source_raw).hexdigest(),
         'prior_manifest_sha256': hashlib.sha256(prior_path.read_bytes()).hexdigest(),
         'limitations': 'Convenience eight pairs. Manual verbatim excerpt selection; prior labels seen. Analyst agreement only, not independent accuracy. Current page snapshots, not historical article versions. Cropping can hide facts. No production deletion or realized savings.',
         'controls': 'Same titles, schema, rules and provider. Only summary field changes. Alternated deterministic arm order; one observation each. No retries, 3.2s interval, $0.01 post-response guard inherited from dedup.execute.'}
    out.mkdir(parents=True, exist_ok=False)
    raw = encoded(m)
    (out / 'manifest.json').write_bytes(raw)
    (out / 'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest())
    print(json.dumps({'cases': len(cases), 'sha256': hashlib.sha256(raw).hexdigest(),
                      'max_request_bytes': max(len(encoded(c['body'])) for c in cases)}))

def continue_prepare(out):
    """Once only: skip every attempted ID, including failures; never retry a 503."""
    raw = (out / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != (out / 'manifest.sha256').read_text():
        raise ValueError('Original manifest changed')
    m = json.loads(raw)
    rows = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
    attempted = {r['id'] for r in rows}
    cases = {c['id']: c for c in m['cases']}
    if len(rows) != len(attempted) or len(cases) != 17 or any(
            r['id'] not in cases or r['request_sha256'] != cases[r['id']]['request_sha256'] for r in rows):
        raise ValueError('Invalid prior attempts')
    if max(json.loads((out / 'run.json').read_text())[k] for k in ('reported_cost_usd', 'reference_cost_usd')) >= .005:
        raise ValueError('Continuation budget unavailable')
    m['cases'] = [c for c in m['cases'] if c['id'] not in attempted]
    if not m['cases']: raise ValueError('No unattempted cases')
    target = out / 'continuation'; target.mkdir(exist_ok=False)
    data = encoded(m)
    (target / 'manifest.json').write_bytes(data)
    (target / 'manifest.sha256').write_text(hashlib.sha256(data).hexdigest())
    print(json.dumps({'remaining': len(m['cases']), 'skipped_attempts': len(rows)}))

def report(out):
    m = json.loads((out / 'manifest.json').read_text())
    rr = [json.loads(line) for line in (out / 'results.jsonl').read_text().splitlines()]
    costs = [json.loads((out / 'run.json').read_text())]
    if (out / 'continuation' / 'results.jsonl').exists():
        rr += [json.loads(line) for line in (out / 'continuation' / 'results.jsonl').read_text().splitlines()]
        costs.append(json.loads((out / 'continuation' / 'run.json').read_text()))
    byid = {r['id']: r for r in rr}
    cases = {c['id']: c for c in m['cases']}
    if len(byid) != len(rr) or len(rr) > 17 or any(r['id'] not in cases or r['request_sha256'] != cases[r['id']]['request_sha256'] for r in rr):
        raise ValueError('Duplicate, extra or modified request')
    result = {'attempted': len(rr), 'valid': sum(r['status'] == 'ok' for r in rr), 'arms': {}, 'pairs': []}
    for arm in ('sparse', 'enriched', 'reverse'):
        cs = [c for c in m['cases'] if c['group'] == arm]
        good = [(c, byid[c['id']]) for c in cs if byid.get(c['id'], {}).get('status') == 'ok']
        result['arms'][arm] = {
            'planned': len(cs), 'valid': len(good),
            'analyst_agreement': sum(c['expected'] == r['relation'] for c, r in good) if arm != 'sparse' else None,
            'false_duplicate_by_analyst_rubric': [c['id'] for c, r in good if c['expected'] not in (None, 'duplicate') and r['relation'] == 'duplicate'],
            'median_ms': statistics.median(r['latency_ms'] for _, r in good) if good else None,
            'input_tokens': sum(r['input_tokens'] for _, r in good),
            'duplicate_candidate_flags': [c['id'] for c, r in good if r['action'] == 'duplicate_candidate_only'],
        }
    for key in EXPECTED:
        result['pairs'].append({'pair': key, 'expected_enriched': EXPECTED[key][0],
             **{arm: byid.get(key + '_' + arm) for arm in ('sparse', 'enriched')}})
    matched = [p for p in result['pairs'] if all(p[a] and p[a]['status'] == 'ok' for a in ('sparse', 'enriched'))]
    result['matched'] = {'pairs': len(matched), **{a: {
        'median_ms': statistics.median(p[a]['latency_ms'] for p in matched) if matched else None,
        'input_tokens': sum(p[a]['input_tokens'] for p in matched),
    } for a in ('sparse', 'enriched')}}
    result['reverse'] = byid.get('R01_reverse')
    result['cost'] = {k: sum(c[k] for c in costs) for k in costs[0]}
    result['cost']['wall_time_excludes_manual_pause'] = True
    result['limitations'] = m['limitations']
    (out / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'report', 'continue-prepare']); p.add_argument('out', type=Path)
    p.add_argument('--sources', type=Path); p.add_argument('--prior', type=Path)
    a = p.parse_args()
    if a.command == 'prepare': prepare(a.out, a.sources, a.prior)
    elif a.command == 'continue-prepare': continue_prepare(a.out)
    else: report(a.out)
