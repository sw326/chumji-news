# Issue Draft: migrate fresh-food price collection and snapshots to ops shadow job

Parent: sw326/openclaw_v2#16
Depends on: #11 inventory, #12 repository bootstrap, #13 web preservation path

## Goal

Create an ops-owned shadow implementation for fresh-food price collection,
snapshot generation, and web-ready artifacts without changing Vercel
production, Supabase production, live schedulers, or existing fresh-food output
paths.

## Inputs

- Fresh-food product/source list identified by the #11 inventory.
- Legacy snapshot format and sample outputs.
- Approved non-production web artifact destination for preview comparison.
- Provider rate-limit and robots/terms notes captured during implementation.

## Outputs

- Local shadow price snapshot artifact.
- Normalized product price records with source timestamp and dedupe key.
- Preview-only web artifact bundle, not deployed to production.
- Job-run summary and last-success marker.

## Schedule

- Intended cadence: inactive metadata only, matching the legacy collection
  cadence after confirmation from #11 inventory evidence.
- No cron, LaunchAgent, LaunchDaemon, Vercel deploy hook, or production scheduler
  may be created or edited in this issue.

## Model, API, And SecretRef Names

- Model policy name: `fresh-food.normalizer.model.default` if normalization
  needs an LLM; otherwise record `none`.
- API references: `fresh-food.sources.http`, `fresh-food.preview.build`.
- SecretRefs: `fresh-food.source.api`, `fresh-food.vercel.preview`,
  `fresh-food.supabase.preview`.
- Production Vercel/Supabase SecretRefs are cutover-only and must not be used by
  the shadow job.

## GUI/Login Dependency

- Expected migration target: no GUI/login dependency.
- Any source requiring a browser login, personal account session, keychain item,
  CAPTCHA solving, or private purchasing account remains under `chumji` or is
  excluded until an approved service-account path exists.

## Shadow Validation

- Run collection with production publication disabled.
- Compare product coverage, price values, timestamps, missing items, and output
  schema against approved legacy samples.
- Build preview-only artifacts and verify they do not target production Vercel
  or production Supabase.

## Duplicate Prevention

- Use snapshot key: `fresh-food:{market}:{observedDate}:{sourceId}`.
- Use product dedupe key based on normalized product ID or canonical source URL.
- Shadow outputs must use a distinct root and must not overwrite legacy
  snapshots or web assets.

## Cutover Approval Gate

Cutover is blocked until a separate approval records Vercel/Supabase project
targets, scheduler change, SecretRef readiness, validation evidence, rollback
plan, and the exact legacy scheduler/output path to retire. This issue must not
perform cutover.

## Rollback

- Keep the legacy collector and deployment path unchanged during shadow work.
- Rollback before cutover is to discard shadow artifacts and preview-only state.
- Future post-cutover rollback must restore the legacy output path and redeploy
  the last known-good production artifact only after approval.

## Completion Evidence

- Contract merged at `jobs/fresh-food/contract.md`.
- Inactive manifest updated with preview SecretRef names only.
- Shadow snapshot and preview artifact paths attached.
- Diff report shows acceptable parity or lists blocked gaps.
- Git status and secret-pattern scan show only intentional, non-secret files.
