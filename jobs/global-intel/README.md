# Global-intel AI-less Shadow Job

This job collects ACLED, GDELT, and OpenSky data and produces a deterministic,
publication-free health and observation report.

It does not call a model, infer military activity from aircraft counts, publish
to Telegram, or modify the disabled legacy global-intel schedule.

Outputs are date partitioned:

- `sources.json`
- `briefing.md`
- `shadow-status.json`

ACLED credentials are optional and referenced through an ops-owned `0600` file.
An authentication failure degrades only ACLED; GDELT and OpenSky continue.
