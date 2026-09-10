# Production news collectors

This directory is the surviving repository copy of the collectors currently
used by the production morning, IT, and trend briefings.

Imported baseline: `sw326/claude-workspace` commit
`f1555d00df4848e873c177f74f9ed88d51e0780c`.

The files preserve the active collection contracts:

- `fetch_morning_news.py`: six general-news RSS sources and production title
  filters;
- `fetch_it_tech.py`: six technology RSS sources and production URL filters;
- `fetch_trends.py`: daily GitHub Trending repositories focused on AI and
  developer tools, recent feed discovery, Hacker News and Lobsters public
  engagement metrics, cross-source article URL deduplication, explicit evidence
  levels, deterministic selection reasons, and an audit artifact. GitHub is
  capped at three records and a layout failure is isolated from other sources.

The production OpenClaw cron runs `run_profile.sh` through the commit-addressed
`~/.openclaw/services/chumji-news-current` link. The old `chumji-ops/jobs/news`
shadow collector is not this production entrypoint.

`adapters/openclaw_gpt_summarize.sh` preserves the active text-only GPT call.
`adapters/publish.py` separates publication from collection and summarization:

- it refuses to overwrite a different briefing for the same date/category;
- an identical rerun is a database no-op;
- an atomic local receipt prevents duplicate Telegram delivery while allowing
  recovery when the database write succeeded but delivery did not;
- credentials are read from files and never accepted as command arguments.

These adapters are connected to the production runner.

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

## GitHub repeat exclusion

The collector excludes repositories introduced in successful News publications
(`news`, `it`, and `trend`) on today and the preceding six KST calendar dates.
The seven-date window advances at midnight Asia/Seoul; a repository becomes
eligible again on the seventh date after its introduction. Same-day successful
publications also count. Collection/audit candidates and unsuccessful attempts
do not count.

The existing publication adapter writes a receipt only after both database
publication and Telegram delivery succeed. The collector reads these receipts
from `CHUMJI_NEWS_RECEIPT_DIR` (default
`~/.local/state/chumji-news/publication-receipts`) and reads repository links
inside each corresponding public article at `https://chumji-news.vercel.app`.
It does not read credentials, change receipts, or call the publication adapter.
`--receipt-dir` supplies an explicit read-only receipt location for verification.
The public article is the content source; receipts identify successful dates
and categories, not scraped drafts. Missing individual receipts are not assumed
to be successes. Missing/empty stores, malformed recent receipts, failed HTTP
reads, and missing article markup produce an explicit history error and omit
GitHub candidates while preserving other sources. No stale/empty fallback is
silently substituted. This depends on retaining the existing success receipts
and public article HTML; layout changes must be fixed before GitHub resumes.

All Trending cards are ranked by the existing relevance/stars/rank policy.
Recent introductions are marked `published_within_7_kst_days` in the audit
before source limits run, allowing lower-ranked new candidates into the maximum
three slots. There is no duplicate backfill when fewer new candidates exist.
The existing prompt already forbids invented additions or target counts.

### Non-publishing validation and rollback

Run the unit suite above, then run only `fetch_trends.py --audit-dir <temporary>`
for a network dry-run. This exercises production collection and history but
never invokes a model, writes a post, or sends a notification. Inspect the
selected output and audit rejection reasons; inject history failures in tests.

Stage a complete `git archive <reviewed-commit>` in a new commit-addressed
release directory, verify its tracked file bytes against Git, and atomically
replace the current symlink. Do not edit the live checkout. Verify the cron
still has its original schedule/argv/delivery and that no in-scope job is running
before cutover. Keep the previous release intact. To roll back this change,
atomically repoint `~/.openclaw/services/chumji-news-current` to retained release
`66a7efecee88438357200757b47ddfa3c61784e8`; do not rerun a publishing job.
