# Current Operations Architecture

Status date: 2026-07-29

This document describes the observed live state. It supersedes older planning
language that described the whole repository as non-production.

## Source of Truth and Discovery

This file is the single declared source of truth for the Mac mini operations
architecture:

`sw326/chumji-ops/docs/operations/current-architecture.md`

Repository roles:

- Development and documentation:
  `/Users/chumji/workspace/chumji-ops`
- Deployed jobs and web source:
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
  +-- KMA / JMA / GDACS / PTWC / SWPC - live alert hub
  +-- HoYoLab -------------------------- live daily check-in
  |
  v
Mac mini, ops account
  |
  +-- /Users/ops/services/chumji-ops
  |     +-- apps/web
  |     +-- jobs/news
  |     +-- jobs/fresh-food
  |     +-- jobs/global-intel
  |     +-- services/alert-hub
  |
  +-- /Users/ops/services/earthquake-alert
  +-- /Users/ops/services/hoyolab-auto
  +-- Investment Assistant runtime
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
| Disaster alert hub | `ops` | always-on LaunchDaemon | production | Telegram |
| HoYoLab check-in | `ops` | LaunchDaemon, 05:05 | cut over; first scheduled verification pending | HoYoLab account action |
| Morning news shadow | `ops` | LaunchDaemon, 08:10 | shadow | local only |
| IT news shadow | `ops` | LaunchDaemon, 09:10 | shadow | local only |
| Fresh-food shadow | `ops` | LaunchDaemon, 09:30 | shadow | local only |
| Global-intel shadow | `ops` | LaunchDaemon, 09:50 | source-health shadow | local only |
| Trend shadow | `ops` | LaunchDaemon, 13:10 | shadow | local only |
| Legacy morning/IT/trend news | OpenClaw | OpenClaw cron | production | Supabase, Vercel, Telegram path |
| Legacy fresh-food snapshot | OpenClaw | OpenClaw cron, 09:20 | production | Supabase, Vercel, Telegram path |
| Legacy global-intel briefing | OpenClaw | disabled cron | disabled | none |
| Public operations snapshot | `ops` | LaunchDaemon, every 5 minutes | production | Supabase read-only snapshot |
| Integrated web | Vercel | Git deployment | protected preview | read-only preview |
| Investment Assistant | `ops` | always-on LaunchDaemon + internal scheduler | production, read-only | Remote MCP |

## Web and Data Boundaries

- News and price pages read existing Supabase `news_posts` data with the anon
  client.
- Alerts and operations pages read the redacted `ops_public_snapshots` rows.
  Preview fixtures remain only as a fallback when the remote snapshot is
  unavailable.
- The connected Supabase project is displayed as `chumji-finance`; its project
  ref is `sdshtmydiylvtqkbatmb`.
- The preview project does not receive a Supabase service-role key.
- The `ops` exporter holds its service-role key only in an ops-owned SecretRef
  and upserts the two public rows `alerts` and `operations`.
- Shadow jobs do not write to Supabase or send Telegram messages.
- The existing `chumji-news` production project remains authoritative until a
  separate web cutover.

## Runtime Storage

- Development checkout: `/Users/chumji/workspace/chumji-ops`
- Deployment checkout: `/Users/ops/services/chumji-ops`
- Shadow output:
  `/Users/ops/Library/Application Support/chumji-ops/shadow`
- Job logs: `/Users/ops/Library/Logs/chumji-ops`
- Secret files: `/Users/ops/.config/chumji-ops/secrets`
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
`/Users/ops/services/investment-assistant-releases`. As of 2026-07-29 it points
to Claude workspace commit `5cb16f5`, which reads domestic and US Kiwoom
holdings independently, preserves native-currency and KRW-converted values,
and records partial source failures without exposing credentials, account
numbers, or raw broker responses. The previous standalone directory is
preserved as a rollback release.

The previous `ops` workspace path remains temporarily as rollback evidence.
Archive it only after a final reference scan and an approved cleanup.

## Known Gaps

1. Compare five days of AI-less news output and decide the publication cutover.
2. Compare fresh-food shadow and production results before moving publication.
3. Refresh the invalid ACLED credential. ReliefWeb RSS now replaces GDELT as
   the default situation-report source; GDELT remains opt-in for diagnostics.
4. Archive the obsolete `ops` workspace after the rollback retention period.
