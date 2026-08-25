# Global-intel AI-less Shadow Job

This job collects ACLED, ReliefWeb RSS, and OpenSky data and produces a
deterministic, publication-free health and observation report. GDELT remains
an opt-in diagnostic source because its public endpoint repeatedly rate-limits
the Mac mini (`GDELT_ENABLED=1`).

It does not call a model, infer military activity from aircraft counts, publish
to Telegram, or modify the disabled legacy global-intel schedule.

Outputs are date partitioned:

- `sources.json`
- `briefing.md`
- `shadow-status.json`

ACLED credentials are optional and referenced through an ops-owned `0600` file.
An authentication failure degrades only ACLED; ReliefWeb and OpenSky continue.
The ACLED password is never written to output or logs.
