# Batch Migration Wave Plan

Issue: sw326/openclaw_v2#16

This plan decomposes the batch migration wave into shadow-only child issues and
repository contracts. It is based on the completed #11 inventory decision that
OpenClaw, GUI/account-bound automation, personal Telegram conversations, Claude
session dependencies, Gemini auth, and live schedulers stay unchanged until a
separate cutover approval is recorded.

## Non-Destructive Scope

- No OpenClaw cron, crontab, LaunchAgent, LaunchDaemon, tmux, Telegram, Vercel,
  Supabase, Claude, Gemini, or live process changes are approved here.
- All manifests in this branch are examples and inactive.
- All SecretRef entries name lookup metadata only; no secret values are stored.
- Shadow jobs must default to dry-run, local output paths, and no downstream
  publication.

## Child Issue Decomposition

| Family | Contract | Issue body draft | Created issue | Purpose |
| --- | --- | --- | --- | --- |
| news/IT/trend/Reddit | `jobs/news/contract.md` | `docs/planning/issue-news-batch.md` | sw326/openclaw_v2#18 | Migrate briefing collection as an ops-owned shadow job while preserving OpenClaw ownership. |
| fresh-food | `jobs/fresh-food/contract.md` | `docs/planning/issue-fresh-food-batch.md` | sw326/openclaw_v2#17 | Migrate price collection and snapshot generation without Vercel production deployment changes. |
| global-intel | `jobs/global-intel/contract.md` | `docs/planning/issue-global-intel-batch.md` | sw326/openclaw_v2#19 | Migrate world-affairs briefing production with model/API boundaries and duplicate prevention. |

## Repository Contracts

Each batch family contract defines:

- Inputs and authoritative source boundaries.
- Outputs, storage shape, and publication limits.
- Schedule intent as inactive metadata only.
- Model/API/SecretRef names without credential values.
- GUI/login/session dependency classification.
- Shadow validation evidence required before any scheduler work.
- Duplicate-prevention keys and lock strategy.
- Cutover approval gate and rollback evidence.
- Completion evidence for the child issue.

## Wave Gate

The migration wave is ready for implementation only after all child issues are
created and linked back to #16. Each implementation issue remains blocked on
approval before:

- Reading production credential values.
- Running against production data or destinations.
- Installing or editing schedulers.
- Publishing to Telegram, Vercel production, Supabase production, or any live
  OpenClaw path.
- Disabling or changing the legacy job.

## Remaining Approvals

- Approval to import existing job source into this repository.
- Approval for each provider SecretRef lookup path and service account scope.
- Approval to run each shadow job against any production upstream credential.
- Approval to compare against live legacy outputs when that requires production
  data access.
- Approval to cut over, rollback, or stop the legacy scheduler.
