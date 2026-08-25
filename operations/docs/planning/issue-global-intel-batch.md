# Issue Draft: migrate global-intel briefing to ops shadow job

Parent: sw326/openclaw_v2#16
Depends on: #11 inventory, #12 repository bootstrap

## Goal

Create an ops-owned shadow implementation for global-intel briefing production
without changing OpenClaw cron, Telegram delivery, Claude billing or auth,
Gemini auth, Vercel production, Supabase production, or live processes.

## Inputs

- Public world-affairs and risk-monitoring sources identified by the #11
  inventory.
- Legacy global-intel briefing examples approved for comparison.
- Model/API routing policy approved for ops shadow execution.
- Redaction rules for any sensitive source metadata.

## Outputs

- Local shadow global-intel briefing artifact.
- Source citation manifest with timestamps and normalized URLs.
- Job-run summary and last-success marker.
- Diff report comparing coverage, structure, and risk categories to legacy
  output.

## Schedule

- Intended cadence: inactive metadata only, matching the legacy briefing cadence
  after confirmation from #11 inventory evidence.
- No cron, OpenClaw cron, LaunchAgent, LaunchDaemon, or production scheduler may
  be created or edited in this issue.

## Model, API, And SecretRef Names

- Model policy name: `global-intel.briefing.model.default`.
- API references: `global-intel.sources.http`, `global-intel.model.api`.
- SecretRefs: `global-intel.model.api`, `global-intel.telegram.destination`.
- Claude billing/auth and Gemini auth remain unchanged unless a separate
  approval creates ops-owned service credentials.

## GUI/Login Dependency

- Expected migration target: no GUI/login dependency.
- Any source requiring personal browser login, keychain, paid account cookies,
  Claude personal session, Gemini personal auth, or OpenClaw GUI state remains
  under `chumji` and is not migrated by this issue.

## Shadow Validation

- Run shadow mode with publication disabled.
- Compare topic coverage, source citation count, briefing sections, model/API
  routing, and redacted logs against approved legacy examples.
- Record run ID, input window, source counts, model/API names, elapsed time, and
  error categories.

## Duplicate Prevention

- Use run lock key: `global-intel:{inputWindowStart}:{inputWindowEnd}`.
- Use source dedupe keys based on canonical URL or source-specific event ID.
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

- Contract merged at `jobs/global-intel/contract.md`.
- Inactive manifest updated with SecretRef names only.
- Shadow dry-run report path and redacted logs attached.
- Diff report shows acceptable parity or lists blocked gaps.
- Git status and secret-pattern scan show only intentional, non-secret files.
