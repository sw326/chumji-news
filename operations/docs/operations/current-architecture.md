# Current Operations Architecture

Status date: 2026-08-25

This document describes the observed live state. It supersedes older planning
language that described the whole repository as non-production.

## Source of Truth and Discovery

This file is the single declared source of truth for the Mac mini operations
architecture:

`sw326/chumji-news/operations/docs/operations/current-architecture.md`

Repository roles:

- Development and documentation after repository consolidation:
  `/Users/chumji/workspace/chumji-news`
- Production web development and local publication source:
  `/Users/chumji/workspace/chumji-news`
- Transitional deployed operations checkout, until component-by-component
  cutover completes:
  `/Users/ops/services/chumji-ops`
- Standalone runtime services:
  `/Users/ops/services/<service-name>`

Do not edit the `ops` deployment checkout as the normal development workflow.
Make changes in the `chumji` checkout, merge them through GitHub, and deploy a
reviewed commit or project snapshot.

OpenClaw and Claude instruction files contain pointers to this document, not
copies of its component status. Before any service, scheduler, data, or
deployment mutation, read this document and then verify the installed runtime:

- LaunchDaemon definitions and `launchctl` state;
- OpenClaw cron configuration and run history;
- current processes, listeners, and health endpoints;
- Vercel, Supabase, and Telegram configuration in scope.

When the document and runtime differ, stop and reconcile the discrepancy.
Runtime observation describes what is currently happening; this document and
its Git history describe the approved architecture and why it changed.

## Architecture

```text
External sources
  |
  +-- RSS / Reddit / Hacker News ------ news shadow jobs
  +-- Garak Market / KAMIS ------------ fresh-food shadow job
  +-- ACLED / ReliefWeb / OpenSky ----- global-intel shadow job
  +-- EMSC / USGS / KMA / JMA / GDACS / PTWC / SWPC - live alert hub
  +-- HoYoLab -------------------------- live daily check-in
  |
  v
Mac mini, ops account
  |
  +-- /Users/ops/services/chumji-ops (transitional runtime checkout)
  |     +-- jobs/news
  |     +-- jobs/fresh-food
  |     +-- jobs/global-intel
  |     +-- services/alert-hub
  |
  +-- /Users/ops/services/earthquake-alert
  +-- /Users/ops/services/hoyolab-auto
  +-- Investment Assistant runtime
  +-- Orca -> OpenClaw bridge (chumji user LaunchAgent)
  |
  +-- LaunchDaemons ------ deterministic services and shadow jobs
  +-- OpenClaw cron ------ agent-assisted publication and personal briefings
  |
  +-- local outputs and logs
  +-- Supabase
  +-- Telegram
  +-- protected Vercel preview
```

## Component Status

| Component | Runtime owner | Scheduler | State | Publication |
| --- | --- | --- | --- | --- |
| Disaster alert hub | `ops` | always-on LaunchDaemon | production; EMSC WebSocket + USGS one-minute polling | Telegram |
| HoYoLab check-in | `ops` | LaunchDaemon, 05:05 | production; first scheduled run verified | HoYoLab account action |
| Morning news shadow | `ops` | LaunchDaemon, 08:10 | shadow | local only |
| IT news shadow | `ops` | LaunchDaemon, 09:10 | shadow | local only |
| Fresh-food shadow | `ops` | LaunchDaemon, 09:30 | shadow | local only |
| Cathode market pipeline | `ops` | LaunchDaemon, Monday 10:20 | runtime state requires cutover re-verification | local artifact and Supabase path; UI remains preview-only |
| Global-intel shadow | `ops` | LaunchDaemon, 09:50 | source-health shadow | local only |
| Trend shadow | `ops` | LaunchDaemon, 13:10 | shadow | local only |
| Legacy morning/IT/trend news | OpenClaw | OpenClaw cron | production | Supabase, Vercel, Telegram path |
| Legacy fresh-food snapshot | OpenClaw | OpenClaw cron, 09:20 | production | Supabase, Vercel, Telegram path |
| Legacy global-intel briefing | OpenClaw | disabled cron | disabled | none |
| Public operations snapshot | `ops` | LaunchDaemon, every 5 minutes | production | Supabase read-only snapshot |
| News web | Vercel | root `chumji-news` deployment | production | `chumji-news.vercel.app` |
| Retired ops web prototype | Vercel | former `chumji-ops/apps/web` deployment | preview only | `chumji-ops-preview.vercel.app`; no future development |
| Investment Assistant | `ops` | always-on LaunchDaemon + internal scheduler | production, read-only | Remote MCP |
| Orca → OpenClaw bridge | `chumji` | always-on user LaunchAgent | production; registered source Run `--peek --wait` watchers + curated observer Run + local journal | sanitized lifecycle summaries, milestones, and decision requests to owner Telegram DM |

## Web and Data Boundaries

- News and price pages read existing Supabase `news_posts` data with the anon
  client.
- The alerts, operations, and market pages exist only in the retired ops web
  preview. They are not routes in the production `chumji-news` application.
- The connected Supabase project is displayed as `chumji-finance`; its project
  ref is `sdshtmydiylvtqkbatmb`.
- The preview project does not receive a Supabase service-role key.
- The `ops` exporter holds its service-role key only in an ops-owned SecretRef.
  It upserts `alerts` and `operations`; after migration 004 approval it may also
  publish the validated `trade-market` row.
- Shadow jobs do not write to Supabase or send Telegram messages.
- The `chumji-news` Vercel project is the authoritative production web surface
  and continues to build the repository root.
- Read-only checks on 2026-08-25 returned HTTP 404 for `/market`, `/alerts`, and
  `/operations` on production and HTTP 200 for the same routes on
  `chumji-ops-preview`. The preview routes are unfinished prototypes and are
  excluded from repository consolidation.
- The `chumji-ops-preview` project is retained only as rollback evidence during
  consolidation. Neither web project receives a Supabase service-role key.

### Web rollback reference

- Current production deployment observed on 2026-08-25:
  `dpl_C5XMvweEJBFWnBZ2MmniCDbv7xhn`
- Pre-scrap-restoration deployment: `dpl_BRES5LDMHVHavFC8HwLeVW98vb9N`
- Pre-cutover production deployment: `dpl_EKrCjGtvxMBsXqV6yHzicsHUdEhy`
- Roll back by promoting the pre-cutover deployment only if the production
  routes or market data contract fail; the preview project remains available
  for diagnosis.

## Runtime Storage

- Development checkout: `/Users/chumji/workspace/chumji-news`
- Transitional operations deployment checkout:
  `/Users/ops/services/chumji-ops`; do not remove it until every installed
  command path has been migrated and verified
- Commit-addressed consolidated releases:
  `/Users/ops/services/chumji-news-releases/<commit>`
- Promoted consolidated runtime link:
  `/Users/ops/services/chumji-news-current`
- Fresh-food shadow LaunchDaemon: migrated to the promoted consolidated
  runtime on 2026-08-25; the first approved cutover run completed with all
  four expected items and no errors
- Shadow output:
  `/Users/ops/Library/Application Support/chumji-ops/shadow`
- Cathode market-board output:
  `/Users/ops/Library/Application Support/chumji-ops/trade-market-briefing`
- Job logs: `/Users/ops/Library/Logs/chumji-ops`
- Secret files: `/Users/ops/.config/chumji-ops/secrets`
- Orca bridge release: `/Users/chumji/.openclaw/services/orca-openclaw-bridge/current`
- Orca bridge config: `/Users/chumji/.config/orca-openclaw-bridge/config.json`
- Orca bridge state:
  `/Users/chumji/Library/Application Support/orca-openclaw-bridge/state.json`
- Orca bridge logs: `/Users/chumji/Library/Logs/orca-openclaw-bridge*.log`
- Alert configuration: `/Users/ops/.config/earthquake-alert`
- HoYoLab configuration:
  `/Users/ops/services/hoyolab-auto/config.json5` with mode `0600`

Secret values must never be copied into this repository or its documentation.

## Scheduler Boundary

Use a macOS LaunchDaemon for deterministic work that does not need an agent:

- always-on polling services;
- source collection;
- rule-based filtering and rendering;
- account actions with an explicit cutover and rollback guard.

Use OpenClaw cron only when the task needs agent judgment, conversational
context, or direct chat delivery. The target design is:

> Collection, ranking, storage, and publication mechanics are code; model-based
> interpretation is optional and event-driven.

The weekly skill-health audit follows the same boundary. Its deterministic
collector in `operations/jobs/skill-health/` streams recent active-session indexes and
transcripts, then emits only bounded candidate metadata and session references.
The OpenClaw cron performs model judgment on those references; it must not
repeat broad transcript or tool-error enumeration when the collector succeeds.

The Orca bridge is a user LaunchAgent because it integrates the owner-only
OpenClaw Gateway and Telegram DM. It leaves the Gateway loopback-only and opens
only outbound SSH to the company computer. Registered authoritative source Runs
are watched with non-consuming `check --peek --wait`; current coordinator
handles are resolved dynamically from Run IDs, and source Deliveries are never
ACKed by the bridge. A dedicated observer Run carries only curated status
milestones. Owner answers return as control mail to the authoritative source
Run, whose coordinator retains reply and gate authority.

## `claude-workspace` Assessment

`/Users/ops/services/claude-workspace` is not required as a general workspace
for the Mac mini server. The live Investment Assistant dependency was moved on
2026-07-29 to a standalone service path:

```text
/Users/ops/services/
  chumji-ops/
  earthquake-alert/
  hoyolab-auto/
  investment-assistant/
```

Development remains at
`/Users/chumji/workspace/claude-workspace/project/investment-assistant-pack`.
Committed project snapshots are staged for `ops`; the service account does not
pull the full workspace. Credentials and mutable data remain under
`/Users/ops/Library/Application Support/InvestmentAssistant`.

The live path is a symlink to a commit-addressed release under
`/Users/ops/services/investment-assistant-releases`. As of 2026-07-30 it points
to Claude workspace commit `dc59b2c`, which supports up to three independently
encrypted Kiwoom connections per user, isolates tokens and failures by
`connection_id`, and stores both connection-level and aggregate snapshots.
Domestic and US holdings remain independently readable, native-currency and
KRW-converted values are preserved, and partial failures do not expose
credentials, account numbers, or raw broker responses. MCP discovery now
provides Korean display names, request aliases, examples, and a read-only help
tool while preserving the stable English tool identifiers. The prior
`2f547ed` and `5cb16f5` releases remain available for rollback.

The previous `ops` workspace path remains temporarily as rollback evidence.
Archive it only after a final reference scan and an approved cleanup.

## Known Gaps

1. Compare five days of AI-less news output and decide the publication cutover.
2. Compare fresh-food shadow and production results before moving publication.
3. Refresh the invalid ACLED credential. ReliefWeb RSS now replaces GDELT as
   the default situation-report source; GDELT remains opt-in for diagnostics.
4. Archive the obsolete `ops` workspace after the rollback retention period.
5. Replace the validated renewable SSH long-wait with direct Orca federation
   only after the saved company runtime identity is refreshed and a full
   control-mail round trip passes.
