# Fresh-food Collector

This job owns the deterministic fresh-food collector used by the production
price snapshot pipeline under `operations/producers/prices/`.

It collects Garak Market wholesale and data.go.kr KAMIS retail data for 배추,
대파, 양파, and 무.

The runner writes a date-partitioned `report.json`, self-contained HTML
snapshot, and `shadow-status.json`. Collection itself contains no Supabase,
Vercel, Telegram, or model integration; publication remains a separate layer.

## Secret references

- `fresh-food.source.data-go-kr` → ops-owned data.go.kr key file
- `fresh-food.source.garak` → ops-owned Garak Market password file

Values remain outside Git with mode `0600`.

## Manual shadow run

```bash
/usr/bin/python3 -B jobs/fresh-food/run_shadow.py \
  --output-root "/Users/ops/Library/Application Support/chumji-ops/shadow/fresh-food" \
  --data-key-file "/Users/ops/.config/chumji-ops/secrets/data-go-kr-api-key" \
  --garak-password-file "/Users/ops/.config/chumji-ops/secrets/garak-publicdata-passwd"
```

Run `operations/producers/prices/run_price_snapshot.sh --dry-run` for the
production validation path without external writes.
