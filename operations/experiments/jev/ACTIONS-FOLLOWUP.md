# Local controller follow-up: guards and tool descriptions

2026-09-22 explicit user continuation of news/search only. Prior run and failure
requests remain untouched in the original worktree at commit 4160c33. No company
system, production routing, private wiki egress, publishing, or repository push.

## Changes

- Whitespace/empty news excerpts have only defer available and are handled by
  code before any model call. This is a mechanical absence check, NOT proof that
  every nonempty excerpt is semantically sufficient.
- Same URL with changed text is NOT a duplicate. Exact URL+excerpt is still code.
- Search may expose the secondary index's common name, scope, query contract and
  coverage limits. This metadata is identical for all described-arm queries and
  contains no answer/expected label. The query, documents, graph, choices and
  instructions are otherwise identical across the two conditions.
- New events and attachments retain canonical-source identity metadata.

## Frozen design

News: four fictional fixtures (empty, whitespace, exact copy, same-URL date
correction). Three code paths, one Jev request. Not new public-news accuracy data.
Search: four NEW authored questions on newly fetched Python pathlib, subprocess,
functools and shutil documentation, six verbatim excerpts. Conditions are paired:
control with no index description, described with the common catalog. There are
eight independent episodes, at most three steps each. The starting graph/hits are
constructed, not a real wiki index. An unavailable answer case accepts either
immediate handoff or one extra index search followed by handoff.

Only field `tool_catalog` differs in paired initial request state. Adjacent pairs,
condition-first order alternates; no randomized replication, alias/version pinning,
or cache disabling. An observed change is hypothesis evidence, not a causal
estimate or general accuracy claim. Previous failed inputs are not reissued.

Executed nonsemantic baseline: materialize all six documents for every question,
zero model calls. This has no sufficiency decisions and is not an answerer. Compare
unique document exposure/characters and actual Jev calls/tokens/list-price costs,
extra retrieval actions, terminal outcomes, missed evidence, and handoffs. A small
packet is not success if required evidence was missed. No downstream writer runs
in either arm; do NOT claim an existing LLM call or reviewer minute was saved.

Fixture SHA256: 2de9397a7af1246969da115ea64a6a543a359072d20247ff697d64d178cf36f8
News round1: cc491cab0a5f9d0488b894213037083f216bc6c311bccf2541ef2e4947aac19a
Search round1: 4d330994f939aa5dc3542d7c3a69d016427ef2004f54923345fcb75abfe11378

No more than 28 requests, Python 3.11 protected Gateway execution, public/synthetic
fixtures only. Existing 3.2s pacing, 30s timeout, no retries, $0.01 post-response
observed/list-cost guard (not a hard invoice cap). Freeze later states before
calling. Any wrong sufficient return, wrong merge or unavailable action remains
in the record. Do not tune or re-call to make the sample pass.

## Reproduce

```sh
python3.11 -m unittest discover -s operations/experiments/jev -p 'test*.py'
python3.11 operations/experiments/jev/action_followup.py fixture FIXTURE --search SEARCH_FIXTURE
python3.11 operations/experiments/jev/actions.py setup OUT --fixture FIXTURE
python3.11 operations/experiments/jev/action_followup.py baseline OUT
# Protected Gateway only:
python3.11 operations/experiments/jev/actions.py run OUT --public-data-no-zdr
python3.11 operations/experiments/jev/action_followup.py compare OUT
```

State/provenance/results live outside Git under
~/.local/state/jev-experiment/action-followup-20260922{,-prep}/.
The previous ACTIONS.md describes the original pilot, whose executable source is
preserved at 4160c33 and /Users/chumji/workspace/chumji-jev-actions.

## Outcome

12 Jev calls succeeded. News: three code actions and one correct model-selected
update on the same-URL correction; all four synthetic guards behaved as expected.
Search control reached the frozen goal for 3/4 cases; described reached 4/4. In the
cached_property case, control handed off; described actually ran secondary search
then returned the required excerpt. It also retrieved an unrelated shutil excerpt:
this is not evidence of perfect retrieval precision. Both conditions handed off
the unsupported benchmark request; neither made a premature sufficient return.

For the four questions, control used 5 Jev calls / 5,044 input tokens; described
used 6 calls / 7,394 tokens. Frozen list-cost estimates: $0.000211848 / $0.000310548.
Described accumulated 7 unique-per-episode documents / 3,512 body characters,
versus 24 / 11,428 in the all-document baseline. These are final distinct-document
exposure sums, NOT actual repeated model input, physical reads, human time, or
end-to-end savings. The baseline calls no model and does not decide sufficiency.
One less unnecessary research handoff is a potential downstream benefit, not a
measured avoided production LLM invocation. No downstream writer ran in either arm.

All 12 responses reported $0; overall reference list cost $0.000562254, API median
568.5ms. No invoice/long-term-free or comparative latency claim. Paired initial
requests differ only by catalog. All 12 final-state hashes were unchanged after
network-blocked batch reapplication. Relevant offline tests: 95 pass. No extra
calls, tuning, production integration or private-text egress followed.
