# Jev connectivity smoke test

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
