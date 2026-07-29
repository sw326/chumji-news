# AI-less News Shadow Job

This directory contains an inactive, deterministic briefing generator. It
accepts the JSON shape produced by the existing public-feed collectors and
creates a Markdown briefing plus a machine-readable run report without calling
Claude, OpenAI, Gemini, or another model.

Nothing in this directory publishes to Supabase or Telegram, reads production
credentials, or installs a schedule.

## Run

```bash
python3 jobs/news/ailess_briefing.py \
  --profile morning \
  --input /path/to/articles.json \
  --output-dir /path/to/shadow-output
```

Profiles:

- `morning`: balanced general-news selection.
- `it`: domestic/international technology selection.
- `trend`: community and trend selection with title-based engagement signals.

Each run writes:

- `<profile>-briefing.md`
- `<profile>-report.json`

The input must be a JSON object containing an `articles` array. Each article
uses `source`, `category`, `title`, `url`, and optional `summary` fields.

## Deterministic policy

1. Strip HTML and tracking parameters.
2. Reject records without a title, URL, or source.
3. Deduplicate by canonical URL and normalized title.
4. Score title signals using a versioned per-profile policy.
5. Apply a per-source quota so one feed cannot dominate.
6. Render feed-provided descriptions only; no generated claims are added.

The report records input/selected counts, rejection reasons, source coverage,
policy version, and confirms `model_route: "none"`.

## Validate

```bash
python3 -m unittest discover -s jobs/news/tests -v
```

Cutover remains subject to `contract.md`: compare shadow artifacts with legacy
outputs first, then separately approve publication and scheduler changes.
