# Sequential controller diagnostic — 2026-09-22

User authorized continued local news and search experiments. No company-system
work, production adapters, private-text egress, publication, or repository push.
Reuse actions.py and its protected ledger executor; do not rewrite prior results.

## Pre-call frozen design

- News: six newly fetched NASA excerpts in chronological order, about OFT-2
  (2022) and Crew Flight Test (2024). The grouping unit is explicitly a named
  mission lifecycle, not every launch/landing as a separate event. Five definite
  cases and one boundary: two NASA landing posts differ by one minute, so either
  attach or update is acceptable for the latter, but the target mission must match.
  Add two diagnostics: exact URL+excerpt replay and missing body. They are not
  additional independent public-news observations. Every step starts with the
  actual previous step's event/article/deferred state, never gold restoration.
- Search: six new authored questions and 12 verbatim official Python excerpts,
  5,852 body characters. Initial routed hits are the existing lexical ranker's
  actual primary-index top two. Links and corpus partition are authored.
  Same Jev sufficiency question and common index description in both arms.
  Routed arm may expand links or query the secondary index (top three).
  Fullscan receives all 12 documents and can only return or hand off (one call).
  Adjacent paired initial calls; condition-first order alternates. No repeated
  trials, model-version pin, or controlled provider cache.
- Expected required-document IDs, terminal decisions and rationales are local
  metadata, never prompt fields. Partial/failed execution is not success.
- Metrics: wrong mission merge/split, missed update, boundary separately,
  preservation of all articles, actual final groups; search required evidence,
  premature sufficient return, unnecessary handoff, actual calls/input tokens,
  list-price and response cost, API time, retrieval actions and document exposure.
  Fullscan is now a semantic baseline but uses the SAME model, not a strong LLM.
  Neither arm writes answers; no eliminated production model calls/human minutes.

Fixture SHA256:
`668ddb079231f4e155cae6f5dab1e354144ec1a7cf5f8c1cdcfc69504d24dfa3`

Maximum 44 calls (8 news + 12 search episodes × 3), normally fewer because fullscan
has one decision and two news cases are code-only. Python 3.11 protected Gateway,
3.2s pacing, 30s timeout, no retries. Stop on transport failure and preserve ledger;
observed/list total $0.01 guard is post-response, not an invoice cap. Freeze each
dependent state's request before calling. No post-call tuning to force success.
Relevant offline tests before calls: 99 passed. Source and fixture frozen together
in the pre-call commit; response artifacts stay outside Git.

## Reproduce

```sh
python3 operations/experiments/jev/sequential.py fixture FIXTURE --news NEWS --search SEARCH
python3 operations/experiments/jev/sequential.py setup OUT --fixture FIXTURE
# Protected Gateway only; never print or override the injected credential:
python3.11 operations/experiments/jev/sequential.py run OUT --public-data-no-zdr
python3 operations/experiments/jev/sequential.py report OUT
python3 -m unittest discover -s operations/experiments/jev -p 'test*.py'
```

Artifacts: `~/.local/state/jev-experiment/sequential-20260922{,-prep}`.
Raw NASA snapshots: workspace `scratch/jev-sequential-news-20260922`;
Python snapshots: workspace `scratch/jev-sequential-search-sources-20260922`.
The fixture contains source URLs, selected excerpts, provenance and local labels.
These are selected small English-source examples with mixed Korean queries,
not a general accuracy/industry ROI or production-scale retrieval benchmark.

## Observed outcome: news complete, search blocked

Pre-call source commit: `24a90b7`. Eleven requests were attempted: ten succeeded,
then S05 (routed deepcopy, Q03) returned HTTP 429. Gateway routing metadata says
`typesafe-ai` was at capacity, one provider attempt, no available fallback. This
is the returned explanation, not independently measured provider infrastructure.
No retry, provider-policy change, new key, additional purchase or later wave ran.

News: five definite public cases matched action and mission target, one boundary
attached to the correct mission within its predeclared allowance. Two code-only
diagnostics also passed. The actual stream built two mission groups, retained
all eight ingestions (including the missing-body deferred item), and recorded the
uncrewed-return decision and landing as updates. No gold state restoration. This
is two selected related mission threads, not representative live-stream accuracy.

Search: only Q01 completed both arms, both correct (Counter). Routed/fullscan
used one call each, 1,326/3,270 input tokens and $0.000055692/$0.000137340 list
estimates. API latencies 451/408 ms do not establish a speed ranking. Q02 fullscan
returned; routed actually expanded logging evidence but its second decision was
never attempted. S05 failed and fell back to handoff in code: this is an
infrastructure fallback, NOT Jev choosing an unnecessary research handoff.
Seven initial search calls and the pending logging decision remain unattempted.
Do not compare unpaired totals or report six-question accuracy/cost superiority.

Successful responses: median 442.5 ms, 17,190 input tokens, $0.000721980 list
estimate; ten responses reported $0. The 429 has no known token/billing receipt.
Neither arm ran a downstream writer. Search efficiency remains unresolved.

Post-call changes only hardened partial-report accounting (unattempted != success,
transport fallback != semantic error, unknown billing != known zero); no prompt,
fixture, routing or executor tuning followed results. Relevant tests: 101 pass.
Sixty source/input checks pass. Network-blocked reapplication left all 20 stored
states unchanged; actual predecessor ancestry and eight unique article IDs pass.
The comparison, source checks, replay checks and raw failed response are preserved
under the artifact directory. Normal run refuses the existing failure; any future
continuation requires a separately defined skip-only policy, not a silent retry.
