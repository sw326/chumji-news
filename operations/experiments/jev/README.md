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
