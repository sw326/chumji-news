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
