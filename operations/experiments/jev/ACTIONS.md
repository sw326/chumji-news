# Local action-controller pilot (2026-09-22)

User scope: news event organization and wiki-like search next-action selection.
Company workflows excluded. No production, scheduler, publication, HTTP business
API, model auto-approval, private wiki egress, or non-wiki push/merge.

## Architecture

Public fixture → deterministic candidate retrieval → Jev Choice → allowlist
check → local API adapter → locked atomic JSON state + execution receipt.
Search repeats with actual retrieved documents, at most three choices. It returns
a verbatim document packet or queues a research request, never a generated answer.
No stronger model interprets Jev output during this execution path.

Reuses claims.py/challenge.py protected executor/parser, canonical news URL and
GeekNews source-identity extraction from shadow.py. New dependency: none.
This is a bounded diagnostic, not a general production controller.

News: eight known public pairs each simulated as an independent new arrival
against the same eight seeded events (not a chronological feed), plus one sparse
input and one identical-URL+excerpt code path. Shared original-source identity
improves candidate retrieval but is not semantic equivalence. Never discard an
article. Preserve additions and corrections in an event's update IDs. Similarity
is simple lexical overlap with source identity first, capped at three candidates.
No temporal-entity extraction, scalable index, or ongoing-stream calibration.

Search: six authored questions on six public Python/SQLite/MDN excerpts. Initial
hits and graph edges are constructed test fixtures, NOT private wiki search or
verified live hyperlinks. Cases exercise sufficient evidence, missing conditions,
linked lookup, alternate index, absence, and refutation of an incorrect premise.
S04/S05 may either search first or hand off immediately; both must end in handoff.

## Pre-call contract

- Max 28 calls total; actual news semantic calls: 9; search max 18.
- Python 3.11, TypeSafe-only via protected AI_GATEWAY_API_KEY on Gateway.
- Same existing 3.2s pacing, 30s timeout, no retry, no extra model or tuning.
- $0.01 post-response observed/list-price guard (not hard billing cap).
- Fixture SHA: 1fff066e25413496b5393151d18a0951f97191655209300a35fb1b153f70ef12
- News round1 manifest: 7187ac9d36cd5b8a936ee012a13dbce6c5a807ab4f1bdcf21901debb2b39dfa9
- Search round1 manifest: e6630170b0540c1d57f7c2f1a53f854ff57d6fef63c87e7f4561163866c2e3ba
- Later manifests are generated from actual state transitions, frozen before each
  wave. Labels/provenance paths are never sent. Known prior responses are unused.
- Invalid/unavailable model actions become defer/handoff, marked as fallback,
  and cannot count as model success. Persist original action and fallback reason.
- Stale views, duplicate application, bad distributions, injected response enums,
  and concurrent writers are rejected. Retain failed attempts; interrupted calls
  block continuation under the existing harness.

Success is execution correctness plus casewise routing outcome, NOT general
accuracy, lower cost than an LLM, human usefulness, or deployment approval.
Check final event targets, original preservation, updates, search packet contents,
premature stopping, and handoff. Any mistaken merge/premature return blocks an
unattended-use recommendation; preserve failures without tuning/repeated calls.

## Commands

```sh
python3.11 -m unittest discover -s operations/experiments/jev -p 'test*.py'
python3.11 operations/experiments/jev/actions.py setup OUT --fixture PUBLIC_FIXTURE
# Only via protected Gateway with public/synthetic fixtures:
python3.11 operations/experiments/jev/actions.py run OUT --public-data-no-zdr
python3.11 operations/experiments/jev/actions.py report OUT
```

Outputs are outside Git under ~/.local/state/jev-experiment/action-controllers-20260922/.
The adjacent *-prep directory owns provenance and author labels. The superseded
pre-call directory preserves the uncalled naive candidate-retrieval preparation;
it demonstrated two cross-language candidate misses before source identity reuse.

## Observed outcome (no tuning/re-calls)

16 Jev calls completed. The eight full-excerpt news cases executed the expected
operation and target; the sparse-title diagnostic incorrectly attached instead
of deferring. The exact-copy case was handled by code. All articles were retained.
Five of six search episodes reached their pre-call acceptable terminal outcome.
The linked-lookup case actually read the transaction excerpt and returned it.
The alternate-index case handed off before searching, despite the answer being
in the fixture's secondary index. Index scope/description was NOT exposed in
model state; do not attribute that missed route solely to model capability.
No Jev call selected search_other_index, so that model-to-API path has only offline
unit verification, not demonstrated successful live selection.

API median: 485ms; all 16 replies reported $0; frozen list-price token estimate:
$0.000998886. No independent baseline, production traffic, human study, or total
cost/time superiority. Final states and exact raw-response correspondence are
outside Git with REPORT.md and summary.json. Network-blocked batch reapplication
left all 16 final-state hashes unchanged. 93 relevant offline tests pass.

Conclusion: bounded choices can directly drive local operations without another
LLM. News input sufficiency and search tool descriptions remain requirements for
a next prototype. This pilot does not authorize unattended production routing.
