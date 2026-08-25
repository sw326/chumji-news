# Operations concept and adoption priorities

Status: review  
Observed: 2026-08-25

This review classifies the source imported from `chumji-ops`. Priority means
what should be reconciled or developed next in the surviving repository; it
does not authorize a scheduler, service, credential, database, or deployment
change.

## Product concepts

| Concept | Existing implementation | Product relationship | Decision |
| --- | --- | --- | --- |
| Fresh-food prices | Garak wholesale and KAMIS retail collector, report and HTML generator | Directly powers the existing Prices product | adopt first |
| News briefings | deterministic RSS shadow for news, IT, and trend | Alternative producer for the existing News product | reconcile after fresh-food |
| Cathode trade market | customs and trade-data pipeline with verified JSON/HTML fallback | New specialist market-analysis product | retain backend; defer UI |
| Disaster alerts | multi-source Go alert hub with deduplication and Telegram delivery | Independent real-time notification service | maintain; do not add a news tab |
| Operations status | redacted alert/market snapshot exporter | Supported the retired Operations UI | retire unless another consumer is demonstrated |
| Global intelligence | deterministic ACLED, ReliefWeb, and OpenSky shadow | Experimental observation feed with no active product | archive/hold |

The retired Market, Alerts, and Operations pages are not design baselines. A
future UI must start from a current user need and use the root news visual and
interaction system.

## Operations-only concepts

| Concept | Role | Decision |
| --- | --- | --- |
| Secret handoff | encrypted, short-lived remote credential entry and SecretRef resolution | keep as shared infrastructure; no news UI |
| Orca to OpenClaw bridge | forwards bounded execution milestones and decision requests | keep as shared infrastructure; no news UI |
| Longitudinal audit | bounded owner-only transcript sampling for Wiki Lab analysis | keep outside product navigation |
| Skill health | bounded candidate collection for maintenance review | keep outside product navigation |
| HoYoLab check-in manifest | account automation deployment definition | maintain as standalone service |

Repository colocation does not make these product features. They belong under
`operations/` because the repository is the surviving source owner, but they
must not expand the public application's tabs.

## Priority order

### P0 — close consolidation and stale boundaries

1. Return HTTP 404 for every retired category route and keep retired rows out
   of aggregate news and bookmark queries.
2. Remove the standalone Reddit profile from migration contracts and planning.
3. Inventory every installed command still pointing to
   `/Users/ops/services/chumji-ops`; prepare commit-addressed replacement and
   rollback paths before archiving the old repository.
4. Resolve the observed non-zero last exits for the fresh-food shadow and
   trade-market job before treating either as cutover-ready. The current user
   cannot read the ops-owned logs, so the failure cause remains unverified.

### P1 — fresh-food publication ownership

Fresh-food is the strongest first adoption because the public Prices page and
daily snapshot already use it. Compare current production output with the
operations collector, define artifact retention outside routine dirty Git
state, then add publication adapters and perform an approved shadow/cutover.

### P2 — news, IT, and trend producer reconciliation

The operations shadow changes both source selection and interpretation and has
no Supabase or Telegram publisher. First compare fixtures and output quality,
choose deterministic versus model-assisted interpretation explicitly, and add
idempotent publication adapters. Do not restore the retired Reddit profile.

### P3 — cathode market as a separately justified feature

Keep the validated backend and provenance model. Do not import the old Market
screen. Revisit a root-app UI only after the data job is healthy and a concrete
decision workflow identifies the few metrics worth displaying.

### Maintain without product adoption

Keep the alert hub, secret handoff, Orca bridge, HoYoLab automation,
longitudinal audit, and skill-health collector operationally isolated. Their
next work is source/runtime consolidation and reliability, not public tabs.

### Retire or hold

- Retire the public ops-status exporter after a consumer and reference scan if
  no surface still reads its Supabase rows.
- Keep global-intel disabled and archive its migration plan unless a specific
  briefing need is revived.
- Remove stale preview/UI planning only after it is confirmed unnecessary for
  rollback evidence.

## Evidence boundary

Read-only `launchctl` inspection on the observation date found the alert hub,
secret handoff, and Orca bridge running. Scheduled news shadows, global-intel,
ops-status, HoYoLab, fresh-food, and trade-market were installed but normally
idle between runs. Their last-exit codes were zero except fresh-food and
trade-market, which were one. Exit codes establish a diagnostic need, not the
failure cause or current product value.
