#!/usr/bin/env python3
"""Sequential public-news replay and matched search sufficiency comparison."""
import argparse
import copy
import fcntl
import json
from pathlib import Path
import statistics
import sys
import time
import urllib.request
import actions as a

MAX_CALLS = 44
NEWS_RULE = a.RULES['news'] + ' 이번 사건 단위는 이름이 같은 단일 우주 임무의 진행 전체다. 같은 임무의 발사·귀환 결정·착륙은 후속이고, 같은 기체라도 다른 임무·시험 비행은 별개 사건이다. 게시 날짜도 대조한다.'


def configure():
    a.MAX_CALLS = MAX_CALLS
    a.RULES['news'] = NEWS_RULE


def fixture(news_path, search_path, dest):
    news, search = a.read(news_path), a.read(search_path)
    docs = search['documents']; pairs = []
    for i, c in enumerate(search['cases']):
        initial = [d['id'] for d in a.rank(c['query'], [d for d in docs if d['index'] == 'primary'], limit=2)]
        if initial != c['initial_ids']:
            raise ValueError('Initial retrieval differs from actual primary rank')
        arms = ['routed', 'fullscan'] if i % 2 == 0 else ['fullscan', 'routed']
        for arm in arms:
            pairs.append({**c, 'id': f'S{len(pairs)+1:02}', 'pair_id': f'Q{i+1:02}',
                          'condition': arm, 'describe_tools': True,
                          'initial_ids': initial if arm == 'routed' else [d['id'] for d in docs]})
    f = {'privacy': 'public_and_synthetic_only', 'news': news,
         'search': {**search, 'cases': pairs},
         'design': {'max_calls': MAX_CALLS, 'news_rule': NEWS_RULE,
                    'search_baseline': 'Same Jev sufficiency question after loading all documents. One decision; not zero-cost semantic baseline.',
                    'gate': 'Keep failures. No tuning or retry. No production connection or private data.'}}
    a.validate_fixture(f)
    a.exclusive(dest, f)
    print('fixture', a.hash_obj(f))


def fresh_news(case, previous=None):
    if previous is not None and previous['status'] != 'done':
        raise ValueError('Previous stream step is unfinished')
    return {'status': 'active', 'incoming': copy.deepcopy(case['incoming']),
            'events': copy.deepcopy(previous['events'] if previous else []),
            'articles': copy.deepcopy(previous['articles'] if previous else []),
            'deferred_ids': copy.deepcopy(previous['deferred_ids'] if previous else []),
            'actions': []}


def search_initial(c, f):
    return {'status': 'active', 'query': c['query'], 'found_ids': c['initial_ids'],
            'other_index_used': c['condition'] == 'fullscan', 'actions': [],
            'tool_catalog': f['search']['index_descriptions']}


def setup(root, source):
    f = a.read(source); a.validate_fixture(f)
    catalog = json.load(urllib.request.urlopen('https://ai-gateway.vercel.sh/v1/models', timeout=30))
    model = a.claims.runner.MODELS['jev']
    price = next(x['pricing'] for x in catalog['data'] if x['id'] == model)
    root.mkdir(parents=True, exist_ok=False)
    a.exclusive(root/'fixture.json', f)
    (root/'fixture.sha256').write_text(a.hash_obj(f))
    a.exclusive(root/'prices.json', {model: price})
    for c in f['news']['cases']:
        (root/'news'/c['id']).mkdir(parents=True)
    for c in f['search']['cases']:
        p = root/'search'/c['id']; p.mkdir(parents=True)
        state = search_initial(c, f)
        a.exclusive(p/'initial.json', state); a.exclusive(p/'state.json', state)
        if len(a.claims.runner.encoded(a.request('search', a.search_view(state, f['search']['documents'])))) > 16000:
            raise ValueError('Search initial body exceeds payload bound')
    a.exclusive(root/'rules.json', {'news': NEWS_RULE, 'search': a.RULES['search'], 'max_calls': MAX_CALLS})
    print('setup', a.hash_obj(f))


def news_batch(root, c, index):
    f = a.load_fixture(root); p = root/'news'/c['id']/'state.json'; state = a.read(p)
    view = a.news_view(state); body = a.request('news', view)
    if len(a.claims.runner.encoded(body)) > 16000:
        raise ValueError('News body exceeds payload bound')
    task = {'id': c['id'], 'arm': 'jev', 'body': body, 'sha256': a.hash_obj(body), 'state_sha256': a.hash_obj(state)}
    m = {'domain': 'news', 'round': index, 'fixture_sha256': a.hash_obj(f),
         'rules': NEWS_RULE, 'criteria': a.NEWS, 'models': {'jev': a.claims.runner.MODELS['jev']},
         'max_calls': 1, 'interval_seconds': 3.2, 'observed_cost_guard_usd': .01,
         'catalog_prices': a.read(root/'prices.json'), 'tasks': [task]}
    out = root/f'news-round-{index}'; out.mkdir(exist_ok=False)
    raw = a.claims.runner.encoded(m); (out/'manifest.json').write_bytes(raw)
    (out/'manifest.sha256').write_text(a.claims.digest(raw)); a.validate_batch(out)
    return out


def all_rows(root):
    rows = []
    for p in sorted(root.glob('*-round-*')):
        m = a.validate_batch(p)
        rows += a.claims.read_results(p, m, criteria=m['criteria'])
    return rows


def usage(rows):
    ok = [r for r in rows if r['status'] == 'ok']
    return {'calls': len(rows), 'succeeded': len(ok), 'failed': len(rows)-len(ok),
            'median_ms': statistics.median(r['latency_ms'] for r in ok) if ok else None,
            'input_tokens': sum(r.get('input_tokens',0) for r in rows),
            'list_cost_usd': sum(r.get('list_cost_usd',0) for r in rows),
            'reported_cost_usd': sum(r.get('reported_cost_usd') or 0 for r in rows),
            'reported_cost_known_n': sum(r.get('reported_cost_usd') is not None for r in rows)}


def execute_batch(root, out, continuation_check=None):
    m = a.validate_batch(out); previous = all_rows(root)
    if continuation_check:
        continuation_check(root)
    elif any(r['status'] != 'ok' for r in previous):
        raise ValueError('Prior failure preserved; no retry')
    old = a.claims.read_results(out, m, criteria=m['criteria']); done = {r['id'] for r in old}
    if len(previous) + sum(t['id'] not in done for t in m['tasks']) > MAX_CALLS:
        raise ValueError('Total call limit')
    if sum(max(r.get('reported_cost_usd') or 0, r.get('list_cost_usd') or 0) for r in previous) >= .01:
        raise ValueError('Observed/list cost limit')
    for t in m['tasks']:
        if t['id'] in done: continue
        state = a.read(root/m['domain']/t['id']/'state.json')
        view = a.news_view(state) if m['domain'] == 'news' else a.search_view(state, a.load_fixture(root)['search']['documents'])
        if a.hash_obj(state) != t['state_sha256'] or a.request(m['domain'], view) != t['body']:
            raise ValueError('Stale request before sending')
    if len(done) < len(m['tasks']):
        a.claims.execute(out, len(m['tasks']), bool(continuation_check), validator=a.validate_batch, criteria=m['criteria'])
    rows = a.apply_batch(out)
    if continuation_check:
        continuation_check(root)
    elif any(r['status'] != 'ok' for r in rows):
        raise ValueError('Transport failure: preserved, stopped')
    time.sleep(3.2)


def run(root, continuation_check=None):
    if sys.version_info[:2] != (3, 11): raise ValueError('Protected execution requires Python 3.11')
    f = a.load_fixture(root)
    if a.read(root/'rules.json') != {'news': NEWS_RULE, 'search': a.RULES['search'], 'max_calls': MAX_CALLS}:
        raise ValueError('Rules changed')
    with (root/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if continuation_check: continuation_check(root)
        previous = None
        for index, c in enumerate(f['news']['cases'], 1):
            p = root/'news'/c['id']; initial = fresh_news(c, previous)
            if not (p/'initial.json').exists(): a.exclusive(p/'initial.json', initial)
            if a.read(p/'initial.json') != initial: raise ValueError('Broken stream ancestry')
            if not (p/'state.json').exists(): a.exclusive(p/'state.json', initial)
            state = a.read(p/'state.json')
            if state['status'] == 'active':
                view = a.news_view(state); code = a.exact_news_action(state, view)
                if code:
                    a.commit_action(p/'state.json', a.hash_obj(state), 'news', code, view)
                else:
                    out = root/f'news-round-{index}'
                    execute_batch(root, out if out.exists() else news_batch(root, c, index), continuation_check)
            previous = a.read(p/'state.json')
        for wave in range(1, a.MAX_STEPS+1):
            out = root/f'search-round-{wave}'
            out = out if out.exists() else a.prepare_batch(root, 'search', wave)
            if out: execute_batch(root, out, continuation_check)
    report(root)


def report(root):
    f = a.load_fixture(root); rows = all_rows(root); news = []
    for c in f['news']['cases']:
        p = root/'news'/c['id']/'state.json'
        if not p.exists() or a.read(p)['status'] != 'done':
            news.append({'id': c['id'], 'group': c['group'], 'status': 'incomplete', 'acceptable': False})
            continue
        s = a.read(p); got = s['receipt']
        valid = bool(s.get('history')) and all(h['decision']['valid'] for h in s['history'])
        target_ok = 'event_id' not in c['expected'] or got.get('event_id') == c['expected']['event_id']
        news.append({'id': c['id'], 'group': c['group'], 'receipt': got, 'valid': valid,
                     'acceptable': valid and target_ok and got['api'] in c['allowed_apis'],
                     'target_ok': target_ok, 'origin': s['history'][-1]['decision']['origin'],
                     'article_count': len(s['articles']), 'event_count': len(s['events'])})
    docs = {d['id']: d for d in f['search']['documents']}; search = []
    for c in f['search']['cases']:
        s = a.read(root/'search'/c['id']/'state.json'); rr = [r for r in rows if r['id'] == c['id']]
        enough = set(c['required_ids']) <= set(s['found_ids'])
        valid = bool(s.get('history')) and all(h['decision']['valid'] for h in s['history'])
        terminal = s['status'] in ('returned', 'handoff')
        returned = s['status'] == 'returned'; expected = c['expected_terminal'] == 'return_candidates'
        search.append({'id': c['id'], 'pair_id': c['pair_id'], 'condition': c['condition'],
                       'actions': s['actions'], 'found_ids': s['found_ids'], 'valid': valid, 'status': s['status'],
                       'completed_valid': valid and terminal,
                       'transport_failed': any(r['status'] != 'ok' for r in rr),
                       'goal_met': valid and terminal and returned == expected and (not expected or enough),
                       'premature_return': returned and (not expected or not enough),
                       'unnecessary_handoff': valid and s['status'] == 'handoff' and expected,
                       'failure_fallback_handoff': not valid and s['status'] == 'handoff',
                       'model_calls': len(rr), 'input_tokens': sum(r.get('input_tokens', 0) for r in rr),
                       'api_ms_sum': sum(r.get('latency_ms', 0) for r in rr),
                       'list_cost_usd': sum(r.get('list_cost_usd', 0) for r in rr),
                       'retrieval_actions': sum(x in ('expand_linked_pages','search_other_index') for x in s['actions']),
                       'distinct_documents': len(s['found_ids']),
                       'distinct_body_characters': sum(len(docs[i]['text']) for i in s['found_ids'])})
    sums = ('goal_met','premature_return','unnecessary_handoff','model_calls','input_tokens',
            'api_ms_sum','list_cost_usd','retrieval_actions','distinct_documents','distinct_body_characters')
    done_news = [c for c in f['news']['cases'] if (root/'news'/c['id']/'state.json').exists()]
    final = a.read(root/'news'/done_news[-1]['id']/'state.json') if done_news else {'events':[], 'articles':[]}
    completed_pairs = [pair for pair in sorted({r['pair_id'] for r in search})
                       if len([r for r in search if r['pair_id']==pair and r['completed_valid']]) == 2]
    result = {'fixture_sha256': a.hash_obj(f), 'news': news, 'search': search,
              'final_events': final['events'], 'articles_preserved': len(final['articles']) == len(f['news']['cases']),
              'totals': {arm: {k: sum(r[k] for r in search if r['condition'] == arm) for k in sums} for arm in ('routed','fullscan')},
              'completed_pairs': completed_pairs,
              'paired_totals': {arm: {k: sum(r[k] for r in search if r['condition']==arm and r['pair_id'] in completed_pairs)
                                     for k in sums} for arm in ('routed','fullscan')},
              'usage': usage(rows),
              'limits': ['Selected NASA mission threads, not a representative production stream.',
                         'Unpaired totals are observed partial workload only, not a valid comparison when interrupted.',
                         'Distinct documents/characters mean locally materialized state, including initial packets of unattempted cases; not model reads.',
                         'Authored public-document questions and graph. No private wiki index or downstream writer.',
                         'Fullscan uses the same Jev sufficiency decision; it is not a strong-model baseline.',
                         'Distinct body exposure is not repeated model input; actual input tokens recorded separately.',
                         'API time excludes setup, pacing, review and recovery. No total production ROI claim.']}
    (root/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'news': news, 'totals': result['totals'], 'usage': result['usage']}, ensure_ascii=False, indent=2))
    return result


if __name__ == '__main__':
    configure()
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=['fixture','setup','run','report'])
    p.add_argument('out', type=Path); p.add_argument('--news', type=Path); p.add_argument('--search', type=Path)
    p.add_argument('--fixture', type=Path); p.add_argument('--public-data-no-zdr', action='store_true'); args = p.parse_args()
    if args.action == 'fixture': fixture(args.news, args.search, args.out)
    elif args.action == 'setup': setup(args.out, args.fixture)
    elif args.action == 'run':
        if not args.public_data_no_zdr: raise ValueError('Explicit public-data acknowledgement required')
        run(args.out)
    else: report(args.out)
