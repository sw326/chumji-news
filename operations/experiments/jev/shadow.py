#!/usr/bin/env python3
"""Offline source-first routing on known candidate pairs; never drops or fetches."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
import dedup
from challenge import encoded

spec = importlib.util.spec_from_file_location('news_source_normalizer', Path(__file__).parents[2] / 'producers/news/fetch_trends.py')
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


def canonical(url):
    try:
        parsed = urlsplit(url or '')
        if parsed.username or parsed.password: return None
        return producer.canonical_article_url(url)
    except (ValueError, TypeError):
        return None


def source_identity(snapshot):
    """Only a recognized GeekNews title link, never arbitrary article citations."""
    url = snapshot.get('url', '')
    identity = canonical(url)
    result = {'canonical': identity, 'method': 'article_url', 'url': url}
    if not identity or snapshot.get('status') != 200:
        return result
    p = urlsplit(url)
    if p.hostname != 'news.hada.io' or p.path != '/topic':
        return result
    text = snapshot.get('text', '')
    # Saved web-fetch markdown uses an explicit ▲ marker immediately before title.
    # Unsupported/multiple layouts fail closed to the discussion URL.
    matches = list(re.finditer(r'^▲\s*\n+\[\*\*[^\n]+?\*\*\]\((https?://[^\s)]+)\)\([^\n]+\)', text, re.M))
    if len(matches) != 1:
        return result
    target = matches[0].group(1)
    target_key = canonical(target)
    if not target_key or urlsplit(target).hostname == 'news.hada.io':
        return result
    return {'canonical': target_key, 'method': 'geeknews_title_link', 'url': target,
            'span': list(matches[0].span(1)),
            'snapshot_sha256': hashlib.sha256(text.encode()).hexdigest()}


def route(state, snapshots, cache):
    """Source grouping and semantic classification are separate observations."""
    identities = {s: source_identity(snapshots[s]) for s in ('A', 'B')}
    result = {'identities': identities, 'retain_A': True, 'retain_B': True}
    a, b = (identities[s]['canonical'] for s in ('A', 'B'))
    if a and b and a == b:
        return {**result, 'route': 'code_source_group', 'reason': 'same_source_content_version_unchecked',
                'jev_needed': False, 'semantic_relation': None}
    if not a or not b or not all(state[s].get('summary', '').strip() for s in ('A', 'B')):
        return {**result, 'route': 'review', 'reason': 'missing_url_or_excerpt', 'jev_needed': False,
                'semantic_relation': None}
    body = dedup.body(state); fingerprint = hashlib.sha256(encoded(body)).hexdigest()
    base = {**result, 'route': 'jev_candidate', 'jev_needed': True,
            'request_sha256': fingerprint, 'body': body}
    previous = cache.get(fingerprint)
    if not previous or previous.get('status') != 'ok':
        return {**base, 'reason': 'no_valid_matching_response', 'semantic_relation': None}
    try:
        label, probabilities = dedup.parse({'answers': {'relation': {
            'type': 'choice', 'choice': previous['relation'], 'probabilities': previous['probabilities']}}})
    except (KeyError, ValueError, TypeError):
        return {**base, 'reason': 'invalid_matching_response', 'semantic_relation': None}
    return {**base, 'reason': 'replayed_exact_request', 'semantic_relation': label,
            'probabilities': probabilities, 'observation': dedup.action(state, label, probabilities)}


def replay(manifest_path, snapshots_path, response_paths, out):
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest_path.with_suffix('.sha256').read_text():
        raise ValueError('Manifest changed')
    manifest = json.loads(raw)
    snapshots_raw = snapshots_path.read_bytes()
    if hashlib.sha256(snapshots_raw).hexdigest() != manifest['source_sha256']:
        raise ValueError('Snapshots changed')
    snapshots = {x['id']: x for x in json.loads(snapshots_raw)}
    cache = {}
    for path in response_paths:
        for line in path.read_text().splitlines():
            r = json.loads(line); key = r['request_sha256']
            if key in cache: raise ValueError('Ambiguous duplicate response hash')
            cache[key] = r
    rows = []
    for c in manifest['cases']:
        if c['group'] != 'enriched': continue
        key = c['pair']
        if c['body'] != dedup.body(c['state']) or c['request_sha256'] != hashlib.sha256(encoded(c['body'])).hexdigest():
            raise ValueError('Question/input changed')
        row = route(c['state'], {s: snapshots[key+s] for s in ('A', 'B')}, cache)
        rows.append({'id': key, **row})
    summary = {'pairs': len(rows), 'code_groups': sum(r['route'] == 'code_source_group' for r in rows),
               'jev_candidates': sum(r['jev_needed'] for r in rows),
               'exact_response_replays': sum(r['reason'] == 'replayed_exact_request' for r in rows),
               'review_without_jev': sum(r['route'] == 'review' for r in rows),
               'new_api_calls': 0, 'actual_drops': 0,
               'limitations': 'Selected known pairs and already fetched manual excerpts. No candidate retrieval, production integration, live cache, source-version equivalence, or end-to-end savings measured.'}
    out.mkdir(exist_ok=False)
    (out/'routes.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    (out/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    (out/'jev-queue.json').write_text(json.dumps([{'id': r['id'], 'body': r['body'], 'request_sha256': r['request_sha256']}
         for r in rows if r['jev_needed']], ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--snapshots', required=True, type=Path)
    p.add_argument('--responses', required=True, nargs='+', type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args(); replay(a.manifest, a.snapshots, a.responses, a.out)
