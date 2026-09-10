# Price snapshot production pipeline

`run_price_snapshot.sh` is the sole production entry point for the daily fresh-food price snapshot.

It validates all four configured items before changing any public surface, builds a temporary clean deployment from the current commit, injects the generated graph without modifying the Git worktree, deploys and smoke-checks the dated graph, then updates Supabase and sends the Telegram link.

Staging supports both Git checkouts (committed bytes via `git archive HEAD`)
and immutable archive releases without `.git` (copy the release files).
Archive staging excludes Git metadata, `.env*`, `.vercel`, dependencies, and
build/Python caches. Broken Git metadata is an error, not a fallback to copying
uncommitted files. Credentials and Vercel project references are added only
through the existing explicit runtime paths after staging.

Validate both runtime forms without external publication:

```bash
python3 -m unittest discover -s operations/producers/prices/tests -v
bash -n operations/producers/prices/run_price_snapshot.sh
```

Runtime data and credentials remain outside Git. The runner accepts SecretRef paths through `FRESH_PRICE_*_FILE` environment variables. Use `--dry-run` to collect, validate, and stage without Vercel, Supabase, or Telegram writes.

If collection or validation fails, the runner exits before deployment and the previous public snapshot remains active.
