# Trade Market Briefing Job

This preserved research backend can refresh cathode-material market data from
Korean Customs, US Census, and Eurostat. Its scheduled production job was
retired on 2026-08-25 because the market UI and public snapshot consumer were
removed and no replacement decision metric had been defined.

China GACC data is a manually verified, provenance-bearing snapshot. When the
Korean publication month advances without a matching snapshot, the board is
published with `pending-one-time-verification`; GACC is not treated as an
automated source.

## Preserved boundaries

- Source code: `operations/jobs/trade-market-briefing`
- Output: `/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing`
- Logs: `/Users/ops/Library/Logs/chumji-ops/trade-market-briefing.*.log`
- SecretRef `trade-market.source.data-go-kr`:
  `/Users/ops/.config/chumji-ops/secrets/data-go-kr-api-key`
- SecretRef `trade-market.source.census`:
  `/Users/ops/.config/chumji-ops/secrets/census-api-key`

The secret value is never stored in Git or copied into output artifacts.

## Manual validation

```bash
cd /Users/chumji/workspace/chumji-news/operations/jobs/trade-market-briefing
/usr/bin/python3 -B -m unittest -v test_current_market_board.py test_refresh_current_market.py
/usr/bin/python3 -B refresh_current_market.py \
  --key-file /Users/ops/.config/chumji-ops/secrets/data-go-kr-api-key \
  --census-key-file /Users/ops/.config/chumji-ops/secrets/census-api-key \
  --output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/cathode-current-market.json" \
  --html-output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/deploy/cathode-current.html" \
  --state-output "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/cathode-refresh-status.json" \
  --lock-file "/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing/output/.cathode-refresh.lock"
```

There is no installed schedule. Run this backend manually only when a concrete
decision question defines the required product codes, periods, comparison
currency, and acceptance criteria. The last validated artifact remains
rollback and research evidence rather than a current product surface.
