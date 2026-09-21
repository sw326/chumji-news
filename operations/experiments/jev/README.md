# Jev connectivity smoke test

## Paired stress comparison (2026-09-21)

`challenge.py prepare OUT --pilot PILOT_DIR` freezes 40 inputs, labels and
request hashes before any model response. The 32 synthetic inputs are 12 simple
cases (two per class, including `unknown`), eight semantic boundary cases and
12 copies of the simple cases with an output-hijacking instruction appended.
They are fictional fixtures, not news claims. Eight public articles reuse pilot
items J11–J18 without accuracy labels. This is an author-labeled diagnostic suite,
not an independently annotated or representative production benchmark.

Both arms receive the same title/summary and classification rules; expected
labels, grouping, historic choices and probabilities are not sent. Jev uses one
Choice question; GPT-4.1 nano uses strict JSON Schema with only `topic`, temperature
zero and at most 32 output tokens. This tests a compact LLM, not verbose prose.
Six labels include `unknown`; this deliberately changes the prior five-label
contract. Final topic correctness is compared directly without applying Jev's
uncalibrated confidence threshold as an advantage over the LLM.

Run protected Gateway execution with Python 3.11:

```sh
python3.11 operations/experiments/jev/challenge.py execute OUT \
  --limit 2 --public-data-no-zdr
# After inspecting the two completed records, execute the remaining frozen tasks:
python3.11 operations/experiments/jev/challenge.py execute OUT \
  --limit 78 --public-data-no-zdr
python3.11 operations/experiments/jev/challenge.py report OUT
```

Ordering is seeded, randomized by input and by arm within each pair. Starts are
at least 3.2 seconds apart; no redirects, automatic retries, model fallback
configuration, purchases or publishing. A failure stops the batch. Explicit
`--continue-after-failure` skips the failed request without retry and proceeds
only with unattempted frozen tasks. By default failure blocks continuation.
All attempted tasks are skipped on continuation; do not run concurrent
writers against one output directory. Eighty requests maximum, 16 KB prepared
payload limit, 30-second timeout; $0.01 accumulated observed/reference-cost guard
is post-response, NOT a hard billing cap. Outputs remain outside Git. The public
model catalog's price snapshot is frozen alongside inputs; reference list cost
ignores cache discounts and is not an invoice. Response-reported charges and
latency are retained separately. API latency excludes imposed inter-call waits;
run wall time is also recorded. Provider aliases are not pinned versions; cache
is not disabled. One template of prompt injection tests only that template.

Official compatibility and schema references:
https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions
https://vercel.com/docs/ai-gateway/sdks-and-apis/openai-chat-completions/structured-outputs

Offline preparation for the trend-selection experiment. This does not change
production selection, publish anything, or establish model quality.
Python standard library only; no installation required.

```sh
python3 operations/experiments/jev/smoke.py \
  ~/.cache/cron-chumji-news/trend-audit/2026-09-20.json \
  --output ~/.local/state/jev-experiment/smoke-dry-run.jsonl
```

The default is dry-run with no credentials or network. It samples at most 10
articles round-robin across sources from the last audit run. Baseline selection
is recorded locally, never included in model input, and is not ground truth.
Keep outputs outside Git. Output files are exclusive-created, not overwritten.

For a live run, add `--execute` and use a new output filename. Run through
OpenClaw Gateway execution with the protected `AI_GATEWAY_API_KEY` entry,
allowed host `ai-gateway.vercel.sh`; never put a key in commands or chat.
There are no retries or redirects; any HTTP, schema or cost error stops the run.
Each request has a 30-second timeout and 16 KB payload limit. A post-response
$0.01 accumulated-cost guard stops subsequent calls; it is not a hard billing
limit and cannot prevent the first request exceeding that amount. No automatic
purchase or recharge is performed. Dry-run does not validate API access.

The official Gateway alias is `typesafe-ai/jev`. Record the returned model;
this alias is NOT a pinned TypeSafe version. Verify version pinning before
longitudinal quality comparisons. This small source-balanced smoke sample is
not a representative quality evaluation. Korean/English quality, calibration,
latency percentiles, repeated calls and blinded human labels follow separately.

Official HTTP schema (read 2026-09-20):
https://vercel.com/docs/ai-gateway/modalities/evaluation

This resolves the earlier Python compatibility question: `POST /v1/evaluate`
accepts structured state, Boolean, Score and Choice questions directly.

## Protected-proxy compatibility and access gate

On the tested Mac, Python 3.14.4 rejects the OpenClaw proxy certificate with
`SSLCertVerificationError` code 85 (Missing Authority Key Identifier), before
sending an HTTP evaluation request. The installed `/opt/homebrew/bin/python3.11`
works with its default certificate-chain and hostname verification, inherited
proxy, and injected CA. Use that interpreter here; do not disable TLS checking
or extract the protected credential. No proxy configuration workaround is needed.

An authenticated evaluation attempt on 2026-09-21 returned HTTP 403 mentioning
credit card and free credits, matching the payment-method verification gate in
the official FAQ: https://vercel.com/docs/ai-gateway/faq . No model answer was
received. Adding a payment method and purchasing credits are separate actions;
neither is performed by this tool. Jev's free-tier eligibility remains unverified.
After the owner completes verification, resume with a new output file.
Sanitized evidence stays outside Git under `~/.local/state/jev-experiment/`.

### Public-news test on Hobby

After payment verification cleared, the next request returned `permission_denied`:
per-request `zeroDataRetention` is available only on Pro and Enterprise. Card
verification, plan-feature entitlement, and purchased credit balance are separate
gates. Buying AI Gateway credits is not a Pro plan upgrade.

For this public-article dataset only, add `--public-data-no-zdr` to omit the ZDR
enforcement option. Default behavior still requires ZDR; there is no automatic
fallback after a rejection. This opt-out does not guarantee provider retention
or training policies and must not be reused for private or company data without
separate review. Protected credential injection, TLS verification, and the
single-provider restriction are unchanged.

On 2026-09-21, ten public candidates across five sources passed response-schema
checks without purchasing credits. Latency was 373–536 ms (median 415.5 ms),
and response-reported cost was $0. This is a connectivity observation, not a
quality benchmark or proof of permanently free pricing. Results remain outside
Git in `~/.local/state/jev-experiment/20260921-1032-public-smoke.jsonl`.

Reference: https://vercel.com/docs/ai-gateway/security-and-compliance/zdr

## Frozen 50-article pilot

`compare.py prepare OUTPUT_DIR` is offline. It freezes 50 exact-URL-unique
candidates from the last run of each day, 2026-09-14 through 2026-09-20, keeping
the latest observation for repeated URLs. Sampling is seeded and source-balanced,
not representative of the original traffic proportions. It emits a hashed request
manifest, a blind HTML rating sheet, and an empty label CSV outside Git.

`compare.py execute OUTPUT_DIR` sends 50 baseline requests plus 12 exact repeats,
12 Choice-order reversals, and 12 exploratory rubric variants (86 evaluations).
Score criteria retain their ordinal order. It reuses the smoke schema validator,
protected Gateway key, TLS validation, and single-provider route. Public-news-only
ZDR opt-out is fixed in this pilot; do not use it for private inputs. All input
state fields are allowlisted; original selection and metrics never reach Jev.

The cost stop is $0.01 observed after a response, not a hard spending cap. Requests
start at least 3.2 seconds apart (more conservative than the manifest's initial
1.2-second minimum). No automatic retries: any failure stops the run. After a 429,
wait for the window to clear, then explicitly use `--resume-rate-limit`. This
checks the original manifest hash, preserves failure records, and skips completed
request IDs/arms; it will not resume a non-rate failure. Never blindly rerun a
completed batch. `report` processes saved results without network access.

Repeat agreement includes any upstream caching; underlying model version is not
pinned. Rubric variation is exploratory, not evidence of improved accuracy.
Historic selection is a comparator, never ground truth. Empty summaries confound
source/language comparisons. Independent human labels and a frozen holdout are
required before accuracy, calibration, or production thresholds can be claimed.

Commands (execute only through protected Gateway execution):

```sh
/opt/homebrew/bin/python3.11 operations/experiments/jev/compare.py prepare ~/.local/state/jev-experiment/pilot-20260921
/opt/homebrew/bin/python3.11 operations/experiments/jev/compare.py execute ~/.local/state/jev-experiment/pilot-20260921
/opt/homebrew/bin/python3.11 operations/experiments/jev/compare.py report ~/.local/state/jev-experiment/pilot-20260921
```

## Machine-first topic protocol

The objective is now sufficient task quality with less total latency, expense,
and integration burden, not beating a general LLM's judgment quality. Compare
against a concise structured-output LLM (not an artificially verbose baseline)
when a measured LLM baseline is available. That comparison has NOT been run.
Free-tier $0 receipts do not establish a long-term cost advantage.

`route.py PILOT --out NEW_DIR` replays saved topic answers offline. `--execute`
uses the first ten frozen articles and asks ONLY the unchanged topic question.
Public data on Hobby additionally needs `--public-data-no-zdr`. Default ZDR,
protected credentials and TLS stay intact. No service or publishing integration.

Consumer JSONL always has four fields: `id`, `status`, `topic`, `reason`.
`classified` yields a candidate category, `review` abstains with null category,
and `fallback` requests an existing rule/manual/LLM path without executing it.
Never interpret fallback as category `other` or silently drop the article.
Detailed scores, model alias, request hash, usage and latency stay in separate
local audit JSONL, not the consumer protocol.

The 0.70 top-probability and 0.20 margin checks demonstrate an abstention policy;
they are NOT calibrated accuracy guarantees or approved production thresholds.
The adapter checks enum, numeric ranges, distribution sum and winner consistency.
Any request/schema error stops further requests and emits fallback for remaining
items. There are at most ten live calls, no retries, a 30-second request timeout,
a 3.2-second minimum interval and a post-response $0.01 cost guard.

Verification:

```sh
/opt/homebrew/bin/python3.11 -m unittest discover -s operations/experiments/jev -p test_route.py -v
```

Measure task-level error and abstention rates together with end-to-end time
(including preprocessing, rate-limit waits and fallback), billable token counts,
consumer payload size, retries and maintenance work. Adapter compactness is our
interface design; it is not unique to Jev, and provider response bytes are larger
than the four-field output. Preprocessing and fallback costs must not disappear
from the comparison. Source selection/ranking remains a separate task.

## Directed duplicate/follow-up diagnostic

`dedup.py` asks how new candidate B relates to already processed A:
`duplicate / followup / distinct / unknown`. It never deletes, publishes, or
changes production. Fixture labels are frozen before calls, not independent gold.
Sixteen fictional pairs cover translated/rephrased reports, price/date additions,
restoration/correction/approval, different versions and reviews, missing evidence,
and one embedded instruction. Eight real pairs are an unlabeled convenience
sample from September 14–20 saved candidates, excluding repository-trending rows
and deduplicating exact article URLs with latest observation retained. Discovery
used title SequenceMatcher similarity (threshold .48), then manual choice of
cross-language duplicates and hard negatives; this is not a production retrieval
benchmark. The supplied discovery JSON, its SHA and article URLs identify the
local input; indices refer only to that frozen file. Full articles were not read.
Four reversed synthetic pairs test asymmetric information containment.

Prepare uses no network; execute requires explicit public-only no-ZDR opt-out and
protected Gateway Python 3.11. At most 28 requests, 3.2-second start intervals,
30-second timeout, 16 KB requests, no redirects/retries, stop on first error,
exclusive results file to prevent re-execution. Post-response $0.01 observed or
reference-price guard is NOT a hard spending cap. Reference price is the earlier
2026-09-21 catalog rate of $0.042/million input tokens, not an invoice.

```sh
python3.11 operations/experiments/jev/dedup.py prepare OUT --discovery FROZEN_JSON
# Through protected Gateway execution only:
python3.11 operations/experiments/jev/dedup.py execute OUT --public-data-no-zdr
python3.11 operations/experiments/jev/dedup.py report OUT
python3.11 -m unittest discover -s operations/experiments/jev -p test_dedup.py -v
```

The local observation adapter refuses even a duplicate-candidate flag when either
summary is missing. With both summaries, duplicate probability >=.90 and margin
>=.30 only produces `duplicate_candidate_only`, never a drop action. These are
uncalibrated diagnostic thresholds. Report raw relations separately from this
adapter so conservative abstention cannot hide false duplicate predictions.
No measured downstream LLM savings or calibrated production cutoff is claimed.
