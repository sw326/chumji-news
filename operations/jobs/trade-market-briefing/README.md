# Trade Market Briefing Job

This deterministic job refreshes the cathode-material market board from Korean
Customs, US Census, and Eurostat. It publishes only after validation and keeps
the previous verified JSON and HTML if collection or validation fails.

China GACC data is a manually verified, provenance-bearing snapshot. When the
Korean publication month advances without a matching snapshot, the board is
published with `pending-one-time-verification`; GACC is not treated as an
automated source.

## Runtime boundaries

- Runtime code: `/Users/ops/services/chumji-ops/jobs/trade-market-briefing`
- Output: `/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing`
- Logs: `/Users/ops/Library/Logs/chumji-ops/trade-market-briefing.*.log`
- SecretRef `trade-market.source.data-go-kr`:
  `/Users/ops/.config/chumji-ops/secrets/data-go-kr-api-key`
- SecretRef `trade-market.source.census`:
  `/Users/ops/.config/chumji-ops/secrets/census-api-key`

The secret value is never stored in Git or copied into output artifacts.

## Manual validation

```bash
cd /Users/ops/services/chumji-ops/jobs/trade-market-briefing
/usr/bin/python3 -B -m unittest -v test_current_market_board.py test_refresh_current_market.py
/usr/bin/python3 -B refresh_current_market.py \
  --key-file /Users/ops/.config/chumji-ops/secrets/data-go-kr-api-key \
  --census-key-file /Users/ops/.config/chumji-ops/secrets/census-api-key \
  --output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/cathode-current-market.json" \
  --html-output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/deploy/cathode-current.html" \
  --state-output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/cathode-refresh-status.json" \
  --lock-file "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/.cathode-refresh.lock"
```

The installed LaunchDaemon runs every Monday at 10:20 Asia/Seoul. This cadence
matches monthly source publication while avoiding unnecessary daily API load.
