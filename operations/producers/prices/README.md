# Price snapshot production pipeline

`run_price_snapshot.sh` is the sole production entry point for the daily fresh-food price snapshot.

It validates all four configured items before changing any public surface, builds a temporary clean deployment from the current commit, injects the generated graph without modifying the Git worktree, deploys and smoke-checks the dated graph, then updates Supabase and sends the Telegram link.

Runtime data and credentials remain outside Git. The runner accepts SecretRef paths through `FRESH_PRICE_*_FILE` environment variables. Use `--dry-run` to collect, validate, and stage without Vercel, Supabase, or Telegram writes.

If collection or validation fails, the runner exits before deployment and the previous public snapshot remains active.
