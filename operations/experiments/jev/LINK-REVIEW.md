# Offline news-link review and correction

Scope: review the frozen sequential news experiment and correct relationships
without altering source articles, original input/candidates, model responses,
or first decisions. This is a local CLI/data tool, not a wiki/news UI,
production integration, causal inference, or a new Jev accuracy experiment.

## Commands (Python 3.11)

From `operations/experiments/jev`:

```
python3.11 link_review.py import /absolute/review.json --source /absolute/sequential-run
python3.11 link_review.py inspect /absolute/review.json --article article-4
python3.11 link_review.py correct /absolute/review.json --expected-sha256 HASH --request /absolute/correction.json
```

Import requires completed one-decision news episodes and intact stream ancestry.
It replays each saved transition and binds Jev requests/responses to the saved
candidate view. Source stays read-only except retaining its empty advisory lock.
The destination is exclusive; original raw source and the frozen imported base
remain evidence. `inspect` includes source article, historical candidates,
request/response (where present), initial choice, current assignment and changes.
It does not generate a rationale or promote linkage to causality.

Correction request:

```json
{"id":"review-001","mode":"move","article_id":"article-4","target":"new-article-2","relation":"update","actor":"reviewer","reason":"Explicit review reason"}
```

- `move`: existing event ID; `relation` is `member` or `update`.
- `unlink`: target/relation must be null; leave article unassigned, not deleted.
- `split`: target/relation null; create `manual-<correction id>` event.
- Restore by a new explicit move; historical corrections are never erased.

Each change records request, before/after assignment and predecessor hash.
Exact same correction ID/body is a no-op; reused ID with changed content and
stale snapshot hashes are rejected. A file lock and atomic replace keep state
and correction log together. This is local single-file concurrency, not a
multi-host transaction or tamper-proof audit system. Hashes detect accidental
changes, not adversaries rewriting the entire history. Actor is supplied local
review metadata, not authenticated identity. No model executes these corrections.

## Projection and downstream review

Current groups, seed title, member/update lists, body and source identities are
rebuilt from current assignments. Removed seed/update content does not linger.
Empty event IDs remain reserved with no current title/body; source history is
still available. All source articles remain in the frozen base.

`review_required` traces later decisions that were actually shown the affected
event among their candidates (not only the chosen one). It conservatively
propagates via their historical selected event. This indicates recorded exposure,
not proof of a wrong decision or causal effect; it does not auto-move descendants.
Because changed groups can alter candidate ranking even for previously unseen
events, **all later articles additionally appear in `retrieval_recheck_ids`**.
The smaller exposure set is not a complete safe-to-skip list. Corrections restored
later do not silently clear review history. No automatic model reevaluation or
review-resolution UI is implemented. The revised projection is inspectable,
but live ingestion remains on the existing experiment controller, not this store.

## Offline observations, 2026-09-22

Imported NASA stream: eight preserved articles. In a separately labelled local
exercise, unlink/split/restore of article-4 restored all original assignments
and original event projections, while preserving three correction records and
an empty split event. This is not an assertion that the NASA link was incorrect.
Exact correction replay caused no file change; original run inventory unchanged.

A five-article **scripted** fault placed a Mission A update into Mission B before
another B followup. Repair removed A's text from B and retained all other links.
The followup was marked for review; an unrelated later item was not in recorded
exposure but remains in the broad retrieval-recheck set. No Jev API calls were
made: this demonstrates contamination bookkeeping/recovery, not a measured
rate of Jev error propagation. Tests also cover seed removal, stale requests,
ID reuse, missing target, base/chain drift and injected atomic-write failure.

Evidence (local, not automatically available elsewhere):
`~/.local/state/jev-experiment/link-review-20260922.json` and
`~/.local/state/jev-experiment/link-review-audit-20260922/`.
Validation: component suite `python3.11 -m unittest discover -s
operations/experiments/jev -p 'test_*.py'` and `git diff --check`.

Final validation: 120 component tests passed. Independent review found and fixed
(1) older moved-member replacing an existing event seed and (2) imported decision
origin/metadata not fully bound to code rules or raw Jev response. Existing seed
is now retained while assigned; unsupported origin and inconsistent valid/raw
choice/fallback metadata are rejected. Re-import of all eight real episodes
passed these stricter checks with identical base hash. Final inspections/audit
are `final-inspection.json`, `final-scripted-inspection.json`, `final-audit.json`
in the evidence folder. No model calls or production mutations.
