#!/usr/bin/env python3
"""Explicit skip-only continuation in an exclusive copy of a frozen run."""
import argparse
import fcntl
import hashlib
from pathlib import Path
import shutil
import sequential as s
import actions as a


def inventory(root):
    files = {}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():
            raise ValueError('Symlinks are not continuation artifacts')
        if p.is_file():
            files[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def no_inflight(root):
    if list(root.rglob('inflight.json')):
        raise ValueError('Unknown inflight request; continuation blocked')


def failures(root):
    result = []
    for out in sorted(root.glob('*-round-*')):
        m = a.validate_batch(out)
        for row in a.claims.read_results(out, m, criteria=m['criteria']):
            if row['status'] != 'ok':
                result.append([out.name, a.hash_obj(row)])
    return result


def prepare(source, dest):
    source, dest = source.resolve(), dest.resolve()
    if source == dest or source in dest.parents or dest in source.parents:
        raise ValueError('Source and destination must be separate')
    with (source/'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        no_inflight(source)
        a.load_fixture(source)
        old_failures = failures(source)
        before = inventory(source)
        # copytree refuses an existing destination, preserving unrelated work.
        shutil.copytree(source, dest)
        if inventory(source) != before or inventory(dest) != before:
            raise ValueError('Snapshot changed during copy')
        plan = {'policy': 'skip-all-attempted-stop-on-new-error-v1',
                'source': str(source), 'source_files': before,
                'historical_failures': old_failures, 'max_calls': s.MAX_CALLS}
        a.exclusive(dest/'continuation.json', plan)
        (dest/'continuation.sha256').write_text(a.hash_obj(plan))
        verify(dest)
        print('continuation', a.hash_obj(plan))


def verify(root):
    no_inflight(root)
    plan = a.read(root/'continuation.json')
    if a.hash_obj(plan) != (root/'continuation.sha256').read_text():
        raise ValueError('Continuation plan changed')
    if plan['policy'] != 'skip-all-attempted-stop-on-new-error-v1' or plan['max_calls'] != s.MAX_CALLS:
        raise ValueError('Continuation policy changed')
    source = Path(plan['source'])
    if source.resolve() == root.resolve() or inventory(source) != plan['source_files']:
        raise ValueError('Original evidence changed')
    # Immutable inputs must remain exact; append-only ledgers keep exact old bytes.
    for name, digest in plan['source_files'].items():
        target = root/name
        if name.endswith(('results.jsonl', 'runs.jsonl')):
            if not target.read_bytes().startswith((source/name).read_bytes()):
                raise ValueError('Historical ledger changed')
        elif name.endswith(('manifest.json', 'manifest.sha256', 'initial.json')) or name in ('fixture.json','fixture.sha256','prices.json','rules.json'):
            if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError('Frozen input changed')
    if failures(root) != plan['historical_failures']:
        raise ValueError('New or altered failure; stopped')
    return plan


if __name__ == '__main__':
    s.configure()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare','run','verify'])
    p.add_argument('out', type=Path)
    p.add_argument('--source', type=Path)
    p.add_argument('--public-data-no-zdr', action='store_true')
    args = p.parse_args()
    if args.action == 'prepare':
        if not args.source: p.error('--source required')
        prepare(args.source, args.out)
    elif args.action == 'run':
        if not args.public_data_no_zdr: p.error('Public-data acknowledgement required')
        s.run(args.out, continuation_check=verify)
    else:
        verify(args.out)
        print('continuation evidence verified')
