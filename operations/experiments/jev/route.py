#!/usr/bin/env python3
"""Experimental topic protocol. Offline replay by default; never publishes news."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request
import smoke

# Demonstration policy only: NOT calibrated probabilities or production thresholds.
MIN_PROBABILITY, MIN_GAP = .70, .20
TOPICS = set(smoke.QUESTIONS['topic']['criteria'])


def fallback(article_id, reason):
    return {'id':article_id,'status':'fallback','topic':None,'reason':reason}


def route(article_id, answer):
    """Fixed consumer contract; scores remain in audit, never parsed from prose."""
    try:
        if answer['type']!='choice' or answer['choice'] not in TOPICS:
            raise ValueError('Invalid choice')
        probs=answer['probabilities']
        if set(probs)!=TOPICS or not all(smoke.valid_number(p,0,1) for p in probs.values()):
            raise ValueError('Invalid probability')
        if abs(sum(probs.values())-1)>.02:raise ValueError('Invalid distribution')
        ranked=sorted(probs.values(),reverse=True)
        if probs[answer['choice']] < ranked[0]-.011:raise ValueError('Choice not maximum')
        if ranked[0]<MIN_PROBABILITY or ranked[0]-ranked[1]<MIN_GAP-1e-9:
            return {'id':article_id,'status':'review','topic':None,'reason':'ambiguous'}
        return {'id':article_id,'status':'classified','topic':answer['choice'],'reason':'policy_pass'}
    except (KeyError,TypeError,ValueError,AttributeError):
        return fallback(article_id,'invalid_response')


def request_body(article, public_data_no_zdr):
    # Reuse the input allowlist; do not pass historic decisions or provider scores.
    body=json.loads(smoke.payload(article['body']['state'],public_data_no_zdr=public_data_no_zdr))
    body['questions']={'topic':smoke.QUESTIONS['topic']}
    return json.dumps(body,ensure_ascii=False).encode()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('pilot',type=Path);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--execute',action='store_true');p.add_argument('--public-data-no-zdr',action='store_true')
    a=p.parse_args()
    manifest=json.loads((a.pilot/'manifest.json').read_text())
    old={r['id']:r for r in map(json.loads,(a.pilot/'results.jsonl').read_text().splitlines()) if r['status']=='ok' and r['arm']=='base'}
    articles=manifest['articles'][:10] if a.execute else manifest['articles']
    bodies=[request_body(x,a.public_data_no_zdr) for x in articles]
    if any(len(b)>16000 for b in bodies):p.error('Payload limit exceeded')
    key=os.environ.get('AI_GATEWAY_API_KEY') if a.execute else None
    if a.execute and not key:p.error('Protected Gateway key missing')
    a.out.mkdir(parents=True,exist_ok=False)
    opener=urllib.request.build_opener(smoke.NoRedirect())
    receipts=[]; outputs=[]; total=0.; previous=0.; stop_reason=None
    with (a.out/'audit.jsonl').open('x') as audit,(a.out/'routes.jsonl').open('x') as routes:
        for article,body in zip(articles,bodies):
            id=article['id']; r={'id':id,'mode':'live' if a.execute else 'replay','policy':{'min_probability':MIN_PROBABILITY,'min_gap':MIN_GAP,'calibrated':False}}
            if stop_reason:
                out=fallback(id,'batch_stopped');r['skipped']=True
            elif not article['body']['state'].get('title'):
                out=fallback(id,'invalid_input');r['skipped']=True
            elif not a.execute:
                r['answer']=old[id]['answers']['topic'];out=route(id,r['answer'])
            else:
                time.sleep(max(0,3.2-(time.monotonic()-previous)));previous=time.monotonic()
                r.update(request_sha256=hashlib.sha256(body).hexdigest(),request_bytes=len(body))
                try:
                    q=urllib.request.Request(smoke.ENDPOINT,data=body,headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
                    with opener.open(q,timeout=30) as response:
                        raw=response.read();d=json.loads(raw)
                    r.update(latency_ms=round((time.monotonic()-previous)*1000),response_bytes=len(raw),usage=d.get('usage'),returned_model=d.get('model'))
                    cost=float(d['providerMetadata']['gateway']['cost'])
                    if not math.isfinite(cost) or cost<0:raise ValueError('Invalid cost')
                    total+=cost;r['cost_usd']=cost;r['answer']=d['answers']['topic'];out=route(id,r['answer'])
                    if out['status']=='fallback':stop_reason='invalid_response'
                    if total>=.01:stop_reason='cost_guard'
                except Exception as e:
                    out=fallback(id,'request_failed');r['error_type']=type(e).__name__
                    if isinstance(e,urllib.error.HTTPError):r['http_status']=e.code
                    stop_reason='request_failed'
            r['consumer']=out;receipts.append(r);outputs.append(out)
            audit.write(json.dumps(r,ensure_ascii=False)+'\n');audit.flush()
            routes.write(json.dumps(out,separators=(',',':'))+'\n');routes.flush()
    summary={'mode':'live' if a.execute else 'replay','items':len(outputs),'status_counts':dict(Counter(x['status'] for x in outputs)),
             'reported_cost_usd':total if a.execute else None,'stop_reason':stop_reason,'policy_calibrated':False,
             'consumer_bytes_total':sum(len(json.dumps(x,separators=(',',':')).encode()) for x in outputs),
             'llm_comparison':'not measured; historical comparator is 3-question Jev, not an LLM'}
    valid=[r for r in receipts if 'answer' in r and 'latency_ms' in r]
    if valid:
        comparable=[old[r['id']] for r in valid]
        summary.update(latency_ms_median=statistics.median(r['latency_ms'] for r in valid),
                       topic_agreement_with_prior=sum(r['answer']['choice']==old[r['id']]['answers']['topic']['choice'] for r in valid),
                       comparable_n=len(valid),input_tokens=sum(r['usage']['inputTokens'] for r in valid),
                       prior_input_tokens=sum(r['usage']['inputTokens'] for r in comparable),
                       prior_latency_ms_median=statistics.median(r['latency_ms'] for r in comparable),
                       response_bytes_total=sum(r['response_bytes'] for r in valid))
    (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 1 if stop_reason else 0


if __name__=='__main__':raise SystemExit(main())
