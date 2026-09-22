# Skip-only continuation (2026-09-22)

The user authorized continuing the interrupted controller comparison, while
parking wiki timelines/diagrams. Relation links are interpretation inputs, not
causal conclusions. No UI, production integration, supplier change or private
input is in scope.

## Frozen scope

Continue `sequential-20260922` in an exclusive sibling copy. Preserve original
11 attempts including S05 routed deepcopy HTTP 429. Never resend that failure
or successful requests. Finish seven unattempted initial search tasks and any
subsequent decisions of active episodes, including S04 logging. Original
44-call cumulative bound, payloads, provider, three-step maximum, cost guard,
Python 3.11 and 3.2-second interval remain unchanged. No new experiment labels.

`resume.py prepare OUT --source SOURCE` copies a quiescent run, records exact
source-file inventory and historical failure hashes, and refuses an existing
OUT. `run OUT --public-data-no-zdr` validates this plan under the controller
lock before each batch, preserves historical ledger byte prefixes, skips all
attempted keys, and stops on any new failure. Unknown `inflight.json` blocks
continuation. Normal `sequential.py run` retains its strict failure stop.

This is a single-owner local experiment continuation, not a distributed job
queue or automatic retry policy. Use one prepared copy; creating multiple
copies and running each is not globally deduplicated. Original source must
remain frozen. A hash detects accidental drift, not malicious rewriting of
both plan and hash. New failures cannot be auto-whitelisted in this copy.

## Evaluation

Only pairs with two valid completed episodes enter paired totals. S05 remains
failed regardless of the other arm's eventual completion. Report continuation
calls separately from original calls. Timing spans different wall-clock periods
and excludes setup, pacing and recovery; do not infer production ROI. Missing
failure billing stays unknown. Preserve the prior interrupted report unchanged.

## Verification

Run `/opt/homebrew/bin/python3.11 -m unittest discover -s
operations/experiments/jev -p 'test_*.py'`. Added tests cover exclusive copy,
source/input/ledger/plan drift, unknown inflight, new failures, unchanged normal
strict mode, and actual transport-loop skipping old success/error and stopping
before a later unattempted task after a new error.

## Observed continuation outcome

Source freeze: `59bf711`; resume implementation before calls: `810117e`.
Continuation plan SHA-256:
`dfe6f6b534f7eee7c62963bdbdecc62a509574a187e6ca8d13cf9a431965f62f`.
Evidence is in local `~/.local/state/jev-experiment/sequential-resume-20260922/`
(`continuation.json`, round manifests/results, `comparison.json`,
`continuation-audit.json`). Public fixture unchanged from SEQUENTIAL.md.

Eight new attempts succeeded: S06–S12 initial decisions and S04's second
logging decision. Original 11 attempts, S05 error/fallback state and entire
original directory inventory remain unchanged. Combined: 19 attempted,
18 successful, one historical error. New input 18,672 tokens, list estimate
$0.000784224, reported cost $0 for eight known responses. Historical failed
request billing remains unknown.

Five valid completed pairs (Q01,Q02,Q04,Q05,Q06) meet their preset goals in
both arms: four adequate returns and one warranted handoff per arm. Q03 is
excluded because its routed arm failed; the fullscan arm succeeded.
Routed/fullscan paired totals: 6/5 decisions, 8,270/16,299 input tokens,
$0.000347340/$0.000684558 list estimate, 3,337/2,839ms summed API latency.
Input/list estimate reduced 49.26%; decision count and summed API latency
increased. Repeated prompt tokens are included. Neither total end-to-end
runtime savings nor strong-model replacement ROI is established. This small
selected public graph has only one successful extra-retrieval episode;
provider failure removed another such question from the matched comparison.

Network-disabled rerun of the completed copy made zero transport calls,
preserved all 20 state files and 19 ledger rows, and verified original file
hashes unchanged. This establishes local cached replay, not distributed
exactly-once delivery or recovery from an unknown in-flight request.

Final component suite: 112 tests passed. Additional whole-run offline recovery
tests exercise recorded-success-before-state-apply, new failure blocking the
next run, and KeyboardInterrupt retaining unknown in-flight evidence. Independent
read-only review found no blocking issue within the documented single-copy scope.
