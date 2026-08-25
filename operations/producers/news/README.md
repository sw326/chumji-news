# Production news collectors

This directory is the surviving repository copy of the collectors currently
used by the production morning, IT, and trend briefings.

Imported baseline: `sw326/claude-workspace` commit
`f1555d00df4848e873c177f74f9ed88d51e0780c`.

The files preserve the active collection contracts:

- `fetch_morning_news.py`: six general-news RSS sources and production title
  filters;
- `fetch_it_tech.py`: six technology RSS sources and production URL filters;
- `fetch_trends.py`: recent feed discovery plus official Hacker News metrics,
  explicit evidence levels, deterministic selection reasons, and an audit
  artifact.

They are not scheduled from this directory yet. The existing OpenClaw cron
continues to run the source checkout in `claude-workspace`.

`adapters/openclaw_gpt_summarize.sh` preserves the active text-only GPT call.
`adapters/publish.py` separates publication from collection and summarization:

- it refuses to overwrite a different briefing for the same date/category;
- an identical rerun is a database no-op;
- an atomic local receipt prevents duplicate Telegram delivery while allowing
  recovery when the database write succeeded but delivery did not;
- credentials are read from files and never accepted as command arguments.

These adapters are tested but not connected to a production schedule yet.

`build_prompt.py` and `prompts/` preserve the current production playbook,
profile templates, and prompt constraints. Frozen-input SHA-256 tests detect
any byte-level prompt drift before a model is called; source JSON is validated
but deliberately not reserialized.

`run_profile.sh` is the scheduler entrypoint. It defaults to `--dry-run`; only
an explicit `--publish` performs the idempotent Supabase/Telegram step. Runtime
state and logs live outside the release checkout so a commit-addressed release
can be rolled back without losing delivery receipts.

## Validation

```bash
python3 -m unittest discover -s operations/producers/news/tests -v
bash -n operations/producers/news/adapters/openclaw_gpt_summarize.sh
python3 operations/producers/news/fetch_morning_news.py
python3 operations/producers/news/fetch_it_tech.py
python3 operations/producers/news/fetch_trends.py --audit-dir /tmp/trend-audit
```

Before changing the production cron, compare these outputs with the active
source commit and add the summarization and publication layers as separately
reviewed adapters.
