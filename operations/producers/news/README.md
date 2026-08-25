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
continues to run the source checkout in `claude-workspace`. This copy contains
no model, Supabase, Telegram, or credential handling and therefore cannot
publish by itself.

## Validation

```bash
python3 -m unittest discover -s operations/producers/news/tests -v
python3 operations/producers/news/fetch_morning_news.py
python3 operations/producers/news/fetch_it_tech.py
python3 operations/producers/news/fetch_trends.py --audit-dir /tmp/trend-audit
```

Before changing the production cron, compare these outputs with the active
source commit and add the summarization and publication layers as separately
reviewed adapters.
