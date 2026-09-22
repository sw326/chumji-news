#!/usr/bin/env python3
"""Paired tool-description diagnostic and transparent full-scan work accounting."""
import argparse
import copy
import json
from pathlib import Path
import actions as a


def make_fixture(search_path, fixture_path):
    search = a.read(search_path)
    pairs = []
    for i, case in enumerate(search['cases']):
        conditions = [('control',False),('described',True)] if i % 2 == 0 else [('described',True),('control',False)]
        for condition, describe in conditions:
            pairs.append({**case, 'id': f'S{len(pairs)+1:02}', 'pair_id': f'Q{i+1:02}',
                          'condition': condition, 'describe_tools': describe})
    article = {'id':'seed-sdk','url':'https://example.org/sdk-2','source_identity':'//example.org/sdk-2',
               'title':'가상 사례: 오로라 SDK 2.0 배포 안내',
               'text':'가상 사례: 오로라 SDK 2.0 정식 배포일은 10월 3일이다. 기존 1.x와 호환되지 않는다.'}
    event = {'id':'sdk-event','title':article['title'],'text':article['text'],
             'article_ids':[article['id']],'update_ids':[],'source_identities':[article['source_identity']]}
    news=[]
    variants=[('empty','',{'api':'defer'}),('whitespace',' \n\t ',{'api':'defer'}),
              ('exact-copy',article['text'],{'api':'attach_article','event_id':'sdk-event'}),
              ('same-url-correction','가상 사례: 오로라 SDK 2.0 배포일을 10월 3일에서 10월 10일로 연기한다. 기존 1.x와 호환되지 않는 조건은 유지한다.',
               {'api':'add_update','event_id':'sdk-event'})]
    for i,(group,text,expected) in enumerate(variants,1):
        incoming={**article,'id':f'incoming-{i}','text':text}
        news.append({'id':f'N{i:02}','group':'synthetic_'+group,'incoming':incoming,
                     'events':[copy.deepcopy(event)],'seed_articles':[copy.deepcopy(article)],
                     'expected':expected,'target_id':event['id'], 'rationale':'Input guard/identity diagnostic, not real news.'})
    fixture={'privacy':'public_and_synthetic_only',
             'news':{'cases':news,'provenance':{'design':'Four new fictional scenarios; no real news accuracy claim.'}},
             'search':{**search,'cases':pairs},
             'design':{'pairs':4,'vary_only':'tool_catalog in initial search view',
                       'max_calls':28,'ordering':'Adjacent paired cases; condition first alternates by pair; no randomization/repeats.',
                       'gate':'No publication. Compare terminal correctness, premature returns, handoffs, retrieval operations and read volume. No post-call tuning.'}}
    a.validate_fixture(fixture)
    a.exclusive(fixture_path,fixture)
    print(json.dumps({'fixture_sha256':a.hash_obj(fixture),'news':4,'search_episodes':8,'pairs':4}))


def verify_pair_contract(root):
    f=a.load_fixture(root); lookup={c['id']:c for c in f['search']['cases']}
    groups={}
    for c in lookup.values(): groups.setdefault(c['pair_id'],{})[c['condition']]=c
    for pair, cases in groups.items():
        views={}
        for condition,c in cases.items():
            s=a.read(root/'search'/c['id']/'initial.json')
            views[condition]=a.search_view(s,f['search']['documents'])
        described=copy.deepcopy(views['described']); catalog=described.pop('tool_catalog')
        if described != views['control'] or catalog != f['search']['index_descriptions']:
            raise ValueError('Paired states differ beyond tool catalog')
        for field in ('query','initial_ids','expected_terminal','required_ids','expected_first','acceptable_first'):
            if cases['control'][field]!=cases['described'][field]:raise ValueError('Paired assessment differs')
    return groups


def baseline(root):
    """Actually construct the all-document packets; no semantic decision claimed."""
    f=a.load_fixture(root); groups=verify_pair_contract(root); output=[]
    for pair,cases in groups.items():
        c=cases['control']; packet=copy.deepcopy(f['search']['documents'])
        output.append({'pair_id':pair,'query':c['query'],'packet':packet,
                       'documents_read':len(packet),'text_characters':sum(len(d['text']) for d in packet),
                       'model_calls':0,'semantic_sufficiency_assessed':False})
    a.exclusive(root/'fullscan-baseline.json',output)
    return output


def compare(root):
    f=a.load_fixture(root); verify_pair_contract(root)
    original=a.read(root/'summary.json'); baselines={r['pair_id']:r for r in a.read(root/'fullscan-baseline.json')}
    rows=[]; docs={d['id']:d for d in f['search']['documents']}; states={}
    for path in sorted(root.glob('*-round-*')):
        m=a.validate_batch(path)
        rows+=a.claims.read_results(path,m,criteria=m['criteria'])
    state_rows={r['id']:r for r in original['search']}
    result={'fixture_sha256':a.hash_obj(f),'conditions':{},'pairs':[]}
    for condition in ('control','described'):
        cases=[c for c in f['search']['cases'] if c['condition']==condition]; metrics=[]
        for c in cases:
            s=a.read(root/'search'/c['id']/'state.json'); states[c['id']]=s
            response=[r for r in rows if r['id']==c['id']]
            read_chars=sum(len(docs[id]['text']) for id in s['found_ids'])
            meta=state_rows[c['id']]
            metrics.append({'pair_id':c['pair_id'],'id':c['id'],'actions':s['actions'],
                            'goal_met':meta['terminal_exact'] and (c['expected_terminal']!='return_candidates' or meta['required_found']),
                            'premature_return':meta['premature_return'],'handoff':s['status']=='handoff',
                            'model_calls':len(response),'input_tokens':sum(r.get('input_tokens',0) for r in response),
                            'api_latency_ms_sum':sum(r.get('latency_ms',0) for r in response),
                            'list_cost_usd':sum(r.get('list_cost_usd',0) for r in response),
                            'retrieval_operations':sum(x in ('expand_linked_pages','search_other_index') for x in s['actions']),
                            'documents_read':len(s['found_ids']),'text_characters':read_chars,
                            'fullscan_documents':baselines[c['pair_id']]['documents_read'],
                            'fullscan_characters':baselines[c['pair_id']]['text_characters']})
        result['conditions'][condition]={'cases':metrics,
            'totals':{key:sum(x[key] for x in metrics) for key in ('goal_met','premature_return','handoff','model_calls','input_tokens',
                'api_latency_ms_sum','list_cost_usd','retrieval_operations','documents_read','text_characters','fullscan_documents','fullscan_characters')}}
    for i in range(4):
        control=result['conditions']['control']['cases'][i]; described=result['conditions']['described']['cases'][i]
        result['pairs'].append({'pair_id':control['pair_id'],'control_goal':control['goal_met'],
                               'described_goal':described['goal_met'],'control_actions':control['actions'],
                               'described_actions':described['actions']})
    result['news']={'cases':original['news'], 'code_handled':sum(r['decisions'][0]['origin']=='code' for r in original['news']),
                    'jev_calls':sum(r['id'].startswith('N') for r in rows)}
    result['limits']=['Four authored questions, one call per state, no randomized replication or version/cache control.',
        'All-document baseline is an executed retrieval baseline, not an answerer or a model-quality control.',
        'Fewer documents does not imply lower end-to-end cost: account for extra Jev calls and missed evidence/handoff.',
        'Neither arm calls a downstream writer. No existing production LLM call has actually been eliminated.',
        'Synthetic news cases test guards, not new public-news generalization.',
        'A paired outcome change supports a tool-description hypothesis, not an isolated causal effect estimate.']
    a.exclusive(root/'comparison.json',result)
    print(json.dumps({k:v['totals'] for k,v in result['conditions'].items()},ensure_ascii=False,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['fixture','baseline','compare']);p.add_argument('out',type=Path)
    p.add_argument('--search',type=Path);args=p.parse_args()
    if args.action=='fixture':make_fixture(args.search,args.out)
    elif args.action=='baseline':baseline(args.out)
    else:compare(args.out)
