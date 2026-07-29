# Current Operations Architecture

Status date: 2026-07-29

This document describes the observed live state. It supersedes older planning
language that described the whole repository as non-production.

## Architecture

```text
External sources
  |
  +-- RSS / Reddit / Hacker News ------ news shadow jobs
  +-- Garak Market / KAMIS ------------ fresh-food shadow job
  +-- ACLED / GDELT / OpenSky --------- global-intel shadow job
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
| Integrated web | Vercel | Git deployment | protected preview | read-only preview |

## Web and Data Boundaries

- News and price pages read existing Supabase `news_posts` data with the anon
  client.
- Alerts and operations pages currently use preview fixtures, not the live
  service event stream.
- The preview project does not receive a Supabase service-role key.
- Shadow jobs do not write to Supabase or send Telegram messages.
- The existing `chumji-news` production project remains authoritative until a
  separate web cutover.

## Runtime Storage

- Source checkout: `/Users/ops/services/chumji-ops`
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
for the Mac mini server. The live dependency is specifically:

`project/investment-assistant-pack`

The Investment Assistant LaunchDaemon runs
`remote/index.js` from that path and uses it as its working directory.
Therefore the directory cannot be removed or moved without a service cutover.

Target layout:

```text
/Users/ops/services/
  chumji-ops/
  earthquake-alert/
  hoyolab-auto/
  investment-assistant/
```

Recommended migration:

1. Copy `investment-assistant-pack` to a standalone service directory.
2. Preserve credentials and mutable data in their existing external paths.
3. Update a staged LaunchDaemon definition.
4. Perform one controlled restart and health/OAuth/Kiwoom checks.
5. Preserve the old path for rollback.
6. Archive the remaining `claude-workspace` only after proving no live
   references remain.

This migration requires separate approval because it changes a live financial
data service path and LaunchDaemon.

## Known Gaps

1. Compare five days of AI-less news output and decide the publication cutover.
2. Compare fresh-food shadow and production results before moving publication.
3. Repair ACLED authentication and replace or supplement unreliable GDELT
   queries.
4. Replace alerts and operations preview fixtures with a real event store.
5. Move the Investment Assistant out of the general-purpose workspace.
6. Reconcile installed LaunchDaemon definitions with versioned deployment
   manifests after each completed cutover.
