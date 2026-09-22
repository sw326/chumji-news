#!/usr/bin/env python3
"""Offline #25 replay of #24. No API execution; order is not approval."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time

import change_review
import claims

SOURCE_SHA = '4853fe47110b119c67d01815b4337c9fbc3f67360278695acb159dfe60366e55'
RESULTS_SHA = '4ce4f52586a9f6cbf23aea4e94986e5817303da33a6cf9a57060b4d506751031'
PRIORITY = {'risk': 0, 'unresolved': 0, 'substantive': 1, 'editorial': 2}


def orders(items):
    """Only public review fields and predictions enter this function, never gold."""
    if len({i['id'] for i in items}) != len(items):
        raise ValueError('Duplicate item')
    if any(i['prediction'] not in PRIORITY for i in items):
        raise ValueError('Unknown prediction')
    chronological = sorted(items, key=lambda i: (i['committed_at'], i['id']))
    newest = sorted(items, key=lambda i: (-datetime.fromisoformat(i['committed_at']).timestamp(), i['id']))
    return {'chronological': chronological, 'newest_first': newest,
            'jev_priority': sorted(chronological, key=lambda i: PRIORITY[i['prediction']])}


def metrics(queue, risk_ids):
    ids = [i['id'] for i in queue]
    if len(set(ids)) != len(ids) or not risk_ids <= set(ids):
        raise ValueError('Incomplete or duplicate queue')
    last = max((ids.index(i) + 1 for i in risk_ids), default=0)
    size = lambda i: len(i['before']) + len(i['after'])
    return {'order': ids, 'risk_in_first_4': sum(i in risk_ids for i in ids[:4]),
            'risk_in_first_8': sum(i in risk_ids for i in ids[:8]),
            'last_risk_position': last if risk_ids else None,
            'characters_until_last_risk': sum(size(i) for i in queue[:last]) if risk_ids else None,
            'total_cases': len(queue), 'total_characters': sum(map(size, queue))}


def random_expectation(n, r):
    if not 0 <= r <= n or n < 1:
        raise ValueError('Invalid population')
    return {'risk_in_first_4': min(4, n) * r / n,
            'risk_in_first_8': min(8, n) * r / n,
            'last_risk_position': r * (n + 1) / (r + 1) if r else None}


def load_items(source, metadata):
    if claims.digest((source / 'manifest.json').read_bytes()) != SOURCE_SHA:
        raise ValueError('Not the frozen #24 manifest')
    if claims.digest((source / 'results.jsonl').read_bytes()) != RESULTS_SHA:
        raise ValueError('Not the frozen #24 responses')
    m = change_review.validate(source, 'real')
    rows = claims.read_results(source, m, criteria=change_review.CRITERIA)
    if len(rows) != 16 or any(r['status'] != 'ok' for r in rows):
        raise ValueError('Replay requires all 16 valid existing responses')
    predictions = {r['id']: r['topic'] for r in rows}
    corpus = json.loads((source / 'corpus.json').read_text())
    items, hashes = [], {}
    for case in corpus['cases']:
        after = corpus['sources'][case['segments']['after']['source']]
        raw = (metadata / (after['commit'] + '.json')).read_bytes()
        record = json.loads(raw)
        url = f"https://github.com/{after['repo']}/commit/{after['commit']}"
        if (record['sha'] != after['commit'] or record['parents'][0]['sha'] != after['parent_commit']
                or record['html_url'] != url
                or after['file'] not in {f['filename'] for f in record['files']}):
            raise ValueError('Commit provenance mismatch')
        stamp = datetime.fromisoformat(record['commit']['committer']['date'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
            raise ValueError('Expected UTC commit timestamp')
        hashes[after['commit']] = claims.digest(raw)
        items.append({'id': case['id'], **case['state'], 'prediction': predictions[case['id']],
                      'committed_at': stamp.isoformat(), 'commit_url': url,
                      'file': after['file'], 'source_url': after['url']})
    return items, {c['id'] for c in m['cases'] if c['expected'] == 'risk'}, hashes


def block(text):
    # A source's Markdown/HTML must remain literal even when it contains fences.
    fence = '`' * max(3, max((len(x) for x in text.splitlines() if x and set(x) == {'`'}), default=0) + 1)
    while fence in text:
        fence += '`'
    return fence + 'text\n' + text + '\n' + fence


def packet(queue, title, predictions=False):
    parts = [f'# {title}', '전건 검토용 발췌입니다. 우선순위는 오류 판정이나 승인 신호가 아닙니다. '
             '문서 전체/다른 위치의 문맥은 원문에서 확인하세요. 항목을 생략하지 않습니다.']
    for position, i in enumerate(queue, 1):
        parts.extend([f"## {position}. {i['id']}",
                      f"[{i['file']}]({i['source_url']}) · [변경 이력]({i['commit_url']}) · {i['committed_at']}"])
        if predictions:
            parts.append('Jev 분류: ' + i['prediction'])
        parts.extend(['### 변경 전', block(i['before']), '### 변경 후', block(i['after'])])
    return '\n\n'.join(parts) + '\n'


def replay(source, metadata, out):
    started = time.perf_counter()
    items, risk_ids, hashes = load_items(source, metadata)
    queues = orders(items)
    summary = {'issue': 'https://github.com/sw326/chumji-wiki/issues/25',
               'source_manifest_sha256': SOURCE_SHA,
               'source_results_sha256': claims.digest((source / 'results.jsonl').read_bytes()),
               'commit_metadata_sha256': hashes, 'additional_api_calls': 0,
               'confirmed_risk_n': len(risk_ids), 'ambiguous_n': 2,
               'priority_rule': PRIORITY, 'queues': {k: metrics(v, risk_ids) for k, v in queues.items()},
               'random_order_expectation': random_expectation(len(items), len(risk_ids)),
               'human_review': 'not_measured', 'time_savings': 'not_established',
               'limitations': ['Same known purposive sample, not new accuracy evidence.',
                               'All records retained; ordering does not reduce full review volume.',
                               'Character exposure is not reading time or task complexity.',
                               'Risk means a semantic change, not an incorrect edit.',
                               'Cached replay cost excludes original evidence preparation and API latency.']}
    # New output only; never mutate the original experiment or prior reviewer entries.
    out.mkdir(parents=True, exist_ok=False)
    for name in ('chronological', 'jev_priority'):
        (out / (name + '.md')).write_text(packet(queues[name], name, name == 'jev_priority'))
    (out / 'review-worksheet.json').write_text(json.dumps({
        'status': 'unfilled_not_a_completed_user_study', 'reviewer': None,
        'design_note': 'Do not reuse the same reviewer on this known sample to claim a blind time comparison.',
        'cases': [{'id': i['id'], 'reviewed': False, 'active_seconds': None,
                   'needs_followup': None, 'notes': None} for i in queues['chronological']]}, indent=2))
    summary['offline_replay_seconds'] = time.perf_counter() - started
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('metadata', type=Path)
    p.add_argument('out', type=Path)
    a = p.parse_args()
    print(json.dumps(replay(a.source, a.metadata, a.out), ensure_ascii=False, indent=2))
