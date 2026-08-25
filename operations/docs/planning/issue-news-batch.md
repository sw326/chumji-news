# Issue Draft: migrate news/IT/trend briefing to ops shadow job

Parent: sw326/openclaw_v2#16
Depends on: #11 inventory, #12 repository bootstrap

## Goal

Create an ops-owned shadow implementation for the active news, IT, and trend
briefing batch without changing OpenClaw cron, Telegram delivery, Claude billing
or auth, Gemini auth, Vercel production, Supabase production, or live processes.

## Inputs

- Public news and technology feeds identified by the #11 inventory.
- Trend source snapshots identified by the #11 inventory.
- Public community feeds used as trend discovery sources, without restoring a
  standalone Reddit briefing.
- Legacy output samples for comparison, accessed only after approval if they
  require production credentials or private paths.

## Outputs

- Local shadow briefing artifact under an approved non-production output root.
- Job-run summary using `docs/operations/job-runs.md`.
- Last-success marker using `docs/operations/health.md`.
- Diff report comparing shadow output to the legacy briefing format.

## Schedule

- Intended cadence: inactive metadata only, matching the legacy briefing cadence
  after it is confirmed from #11 inventory evidence.
- No cron, OpenClaw cron, LaunchAgent, LaunchDaemon, or production scheduler may
  be created or edited in this issue.

## Model, API, And SecretRef Names

- Model policy name: `news.briefing.model.default`.
- API references: `news.sources.http`, `news.reddit.api`, `news.model.api`.
- SecretRefs: `news.reddit.oauth`, `news.model.api`, `news.telegram.destination`.
- Secret values must not be read, copied, logged, or committed.

## GUI/Login Dependency

- Expected migration target: no GUI/login dependency for shadow collection.
- Any source requiring browser login, personal keychain, Claude personal session,
  Gemini personal auth, or OpenClaw GUI state remains under `chumji` and must be
  split out before implementation continues.

## Shadow Validation

- Run shadow mode with publication disabled.
- Compare source coverage, item counts, language, citations, and output schema
  against approved legacy samples.
- Record run ID, input window, source counts, model/API names, elapsed time, and
  redacted failure categories.

## Duplicate Prevention

- Use a per-window lock key: `news:{inputWindowStart}:{inputWindowEnd}`.
- Use item dedupe keys based on normalized source URL or upstream ID.
- Shadow mode must write to separate output paths and must not post to Telegram
  or overwrite legacy artifacts.

## Cutover Approval Gate

Cutover is blocked until a separate approval records target revision, scheduler
change, SecretRef readiness, validation evidence, rollback plan, and the exact
legacy scheduler to disable. This issue must not perform cutover.

## Rollback

- Keep the legacy OpenClaw/chumji scheduler unchanged during shadow work.
- Rollback before cutover is to discard shadow artifacts and disable no live
  component because none is enabled.
- Future post-cutover rollback must restore the legacy scheduler from recorded
  evidence and stop only the approved ops scheduler.

## Completion Evidence

- Contract merged at `jobs/news/contract.md`.
- Inactive manifest updated with SecretRef names only.
- Shadow dry-run report path and redacted logs attached.
- Diff report shows acceptable parity or lists blocked gaps.
- Git status and secret-pattern scan show only intentional, non-secret files.
