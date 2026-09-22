#!/usr/bin/env python3
"""Offline, append-only news-link corrections over frozen sequential evidence."""
import argparse
import copy
import fcntl
import json
import os
from pathlib import Path
import tempfile
import actions as a
import sequential as s



def validate_decision(initial, history, response):
    view=a.news_view(initial);origin=history['decision'].get('origin')
    if origin=='code':
        if response is not None or history['action']!=a.exact_news_action(initial,view) or history['decision']!={'origin':'code','valid':True}:
            raise ValueError('Code decision does not match deterministic rule')
    elif origin=='jev':
        if response is None: raise ValueError('Missing Jev response')
        raw=response.get('topic')
        valid=response['status']=='ok' and raw in view['available_actions']
        expected={'origin':'jev','raw_action':raw,'valid':valid,
                  'fallback_reason':None if valid else ('api_error' if response['status']!='ok' else 'unavailable_action')}
        if history['decision']!=expected or history['action']!=(raw if valid else 'defer'):
            raise ValueError('Jev decision metadata differs from response')
    else: raise ValueError('Unsupported decision origin')


def import_run(source, out):
    records = []
    with (source/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        f = a.load_fixture(source)
        previous = None
        for index, case in enumerate(f['news']['cases'], 1):
            folder = source/'news'/case['id']
            initial, state = a.read(folder/'initial.json'), a.read(folder/'state.json')
            if initial != s.fresh_news(case, previous):
                raise ValueError('Broken stream ancestry')
            history = state.get('history', [])
            if state['status'] != 'done' or len(history) != 1:
                raise ValueError('Only completed single-decision news episodes supported')
            h = history[0]; view = a.news_view(initial)
            expected = a.transition('news', initial, h['action'], view)
            expected['history'] = history
            if h['before_sha256'] != a.hash_obj(initial) or h['receipt'] != state['receipt'] or expected != state:
                raise ValueError('State does not replay from recorded decision')
            request = response = None
            if h['decision']['origin'] == 'jev':
                batch = source/f'news-round-{index}'
                manifest = a.validate_batch(batch)
                tasks = [t for t in manifest['tasks'] if t['id'] == case['id']]
                rows = [r for r in a.claims.read_results(batch,manifest,criteria=manifest['criteria']) if r['id']==case['id']]
                if len(tasks)!=1 or len(rows)!=1 or tasks[0]['state_sha256']!=a.hash_obj(initial) or tasks[0]['body']!=a.request('news',view):
                    raise ValueError('Missing or mismatched request evidence')
                request,response = tasks[0],rows[0]
                choice = response.get('topic') if response['status']=='ok' else None
                effective = choice if choice in view['available_actions'] else 'defer'
                if effective != h['action']:
                    raise ValueError('Response and action differ')
            validate_decision(initial,h,response)
            records.append({'episode_id':case['id'], 'article':initial['incoming'],
                            'view':view, 'history':h, 'request':request, 'response':response})
            previous = state
        base = {'source':str(source.resolve()),'fixture_sha256':a.hash_obj(f),'records':records}
        if len({x['article']['id'] for x in records})!=len(records):
            raise ValueError('Duplicate article IDs')
        store={'version':1,'base':base,'base_sha256':a.hash_obj(base),'corrections':[]}
        validate(store)
        a.exclusive(out,store)
    return store


def originals(store):
    assignments={}; events={}
    for rec in store['base']['records']:
        receipt=rec['history']['receipt']; article=rec['article']
        eid=receipt.get('event_id')
        if receipt['api']=='create_event': events[eid]=article['title']
        assignments[article['id']]={'event_id':eid,'relation':'update' if receipt['api']=='add_update' else ('member' if eid else 'deferred')}
    return assignments,events


def change(assignments,events,req,articles):
    aid=req['article_id']; mode=req['mode']; target=req.get('target'); relation=req.get('relation')
    if aid not in assignments or not req['reason'].strip() or not req['actor'].strip():
        raise ValueError('Known article, actor and reason required')
    if mode=='unlink':
        if target is not None or relation is not None: raise ValueError('Unlink has no target/relation')
        value={'event_id':None,'relation':'unlinked'}
    elif mode=='split':
        if target is not None or relation is not None: raise ValueError('Split generates its target')
        eid='manual-'+req['id']
        if eid in events: raise ValueError('Split event collision')
        events[eid]=articles[aid]['title'];value={'event_id':eid,'relation':'member'}
    elif mode=='move':
        if target not in events or relation not in ('member','update'): raise ValueError('Known target and relation required')
        value={'event_id':target,'relation':relation}
    else: raise ValueError('Unknown correction mode')
    if assignments[aid]==value: raise ValueError('No change')
    assignments[aid]=value
    return value


def validate(store):
    if store['version']!=1 or a.hash_obj(store['base'])!=store['base_sha256']:
        raise ValueError('Frozen evidence changed')
    assignments,events=originals(store)
    articles={r['article']['id']:r['article'] for r in store['base']['records']}
    seen=set();previous=store['base_sha256']
    for entry in store['corrections']:
        req=entry['request']
        if not req['id'] or req['id'] in seen or entry['previous_sha256']!=previous:
            raise ValueError('Correction chain changed')
        seen.add(req['id'])
        if assignments.get(req['article_id'])!=entry['before']: raise ValueError('Correction before-state changed')
        after=change(assignments,events,req,articles)
        if after!=entry['after']: raise ValueError('Correction after-state changed')
        previous=a.hash_obj(entry)
    return assignments,events


def projection(store):
    assignments,event_names=validate(store)
    records=store['base']['records']; groups=[]
    seeds={r['history']['receipt']['event_id']:r['article']['id'] for r in records
           if r['history']['receipt']['api']=='create_event'}
    seeds.update({'manual-'+e['request']['id']:e['request']['article_id'] for e in store['corrections']
                  if e['request']['mode']=='split'})
    for eid in event_names:
        members=[r['article'] for r in records if assignments[r['article']['id']]['event_id']==eid]
        updates=[x for x in members if assignments[x['id']]['relation']=='update']
        # Rebuild text from current members: do not retain removed article content.
        seed=next((x for x in members if x['id']==seeds[eid]),members[0] if members else None)
        texts=([seed] if seed else [])+[x for x in updates if not seed or x['id']!=seed['id']]
        groups.append({'id':eid,'title':seed['title'] if seed else None,
                       'text':'\n\n'.join(x['text'] for x in texts),
                       'article_ids':[x['id'] for x in members], 'update_ids':[x['id'] for x in updates],
                       'source_identities':sorted({x['source_identity'] for x in members if x.get('source_identity')}),
                       'empty':not members})
    review={}; retrieval_recheck=set()
    positions={r['article']['id']:i for i,r in enumerate(records)}
    for entry in store['corrections']:
        req=entry['request']; affected={entry['before']['event_id'],entry['after']['event_id']}-{None}
        for rec in records[positions[req['article_id']]+1:]:
            retrieval_recheck.add(rec['article']['id'])
            # All presented candidates count, not just the chosen one. Conservative
            # propagation tracks historical exposure, not causal error attribution.
            candidates={x['id'] for x in rec['view']['candidates']}
            target=rec['history']['receipt'].get('event_id')
            if affected & candidates:
                review.setdefault(rec['article']['id'],[]).append(req['id'])
                if target: affected.add(target)
    return {'assignments':assignments,'events':groups,'review_required':review,
            'retrieval_recheck_ids':[r['article']['id'] for r in records if r['article']['id'] in retrieval_recheck],
            'unlinked_ids':[aid for aid,v in assignments.items() if v['relation']=='unlinked'],
            'deferred_ids':[aid for aid,v in assignments.items() if v['relation']=='deferred'],
            'interpretation':'Link membership and candidate exposure are not causality or confirmed errors.'}


def inspect(store, article_id=None):
    current=projection(store)
    records=[r for r in store['base']['records'] if article_id is None or r['article']['id']==article_id]
    if article_id and not records: raise ValueError('Unknown article')
    return {'store_sha256':a.hash_obj(store),'current':current,'evidence':records,
            'corrections':store['corrections']}


def correct(path, expected_sha256, req):
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        store=a.read(path);assignments,events=validate(store)
        for old in store['corrections']:
            if old['request']['id']==req['id']:
                if old['request']!=req: raise ValueError('Correction ID reused with different content')
                return store  # exact replay is a no-op even with the original hash
        if a.hash_obj(store)!=expected_sha256: raise ValueError('Stale review snapshot')
        if not req['id']: raise ValueError('Correction ID required')
        before=copy.deepcopy(assignments.get(req['article_id']))
        articles={r['article']['id']:r['article'] for r in store['base']['records']}
        after=change(assignments,events,req,articles)
        previous=a.hash_obj(store['corrections'][-1]) if store['corrections'] else store['base_sha256']
        store['corrections'].append({'request':copy.deepcopy(req),'before':before,'after':after,'previous_sha256':previous})
        validate(store)
        fd,name=tempfile.mkstemp(dir=path.parent,prefix=path.name+'.',suffix='.tmp')
        try:
            with os.fdopen(fd,'w') as f:
                json.dump(store,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
            os.replace(name,path)
        finally:
            if os.path.exists(name):os.unlink(name)
        return store


if __name__=='__main__':
    s.configure()
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['import','inspect','correct']);p.add_argument('store',type=Path)
    p.add_argument('--source',type=Path);p.add_argument('--article');p.add_argument('--request',type=Path)
    p.add_argument('--expected-sha256');args=p.parse_args()
    if args.action=='import':
        if not args.source:p.error('--source required')
        result=import_run(args.source,args.store)
        print(json.dumps({'store_sha256':a.hash_obj(result),'articles':len(result['base']['records'])}))
    elif args.action=='inspect': print(json.dumps(inspect(a.read(args.store),args.article),ensure_ascii=False,indent=2))
    else:
        if not args.request or not args.expected_sha256:p.error('--request and --expected-sha256 required')
        result=correct(args.store,args.expected_sha256,a.read(args.request))
        print(json.dumps({'store_sha256':a.hash_obj(result),'current':projection(result)},ensure_ascii=False,indent=2))
