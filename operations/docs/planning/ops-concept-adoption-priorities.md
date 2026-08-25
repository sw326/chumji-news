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
   trade-market job before treating either as cutover-ready. Read-only log
   inspection found that the old fresh-food collector timed out on all four
   items while using the pre-hardening HTTP implementation. The trade-market
   validator preserved its last good output because automated sources were not
   all complete; the specific source was not recorded in the failure status.

The fresh-food source fix was merged as `cb35ce9` and staged as a
commit-addressed release. A manual run as the `ops` user on 2026-08-25 covered
all four expected items with collector exit code zero and no reported errors.
After explicit approval, the installed LaunchDaemon was moved to consolidated
release `191e7de` through `chumji-news-current`. Its first cutover run again
covered all four items with collector exit zero and no reported errors. The
pre-cutover plist and transitional checkout remain available for rollback.

### P1 — fresh-food publication ownership

Fresh-food is the strongest first adoption because the public Prices page and
daily snapshot already use it. Compare current production output with the
operations collector, define artifact retention outside routine dirty Git
state, then add publication adapters and perform an approved shadow/cutover.

### P2 — news, IT, and trend producer consolidation

The rejected operations shadow changed both source selection and interpretation
and had no Supabase or Telegram publisher. It has been retired instead of
becoming a second producer. Future work imports the active production
collectors into this repository, chooses model-assisted interpretation
explicitly, and adds idempotent publication adapters. Do not restore the
retired Reddit profile.

The first same-day cited-URL sample found only 2/14 shadow morning URLs and
1/8 shadow IT URLs in their production counterparts. This rules out a direct
AI-less scheduler replacement. Preserve the production collectors as the
baseline and treat model usage and publication as later independent decisions.

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
trade-market, which were one. The fresh-food source in this repository lagged
the production skill's HTTPS, retry, and request-sharing hardening. The source
fix does not alter the installed LaunchDaemon; runtime validation remains a
separate cutover step. Direct live validation from the development worktree was
not forced: the `ops` user cannot read the owner worktree and the owner user
cannot read the ops SecretRef. Validate the exact commit only after staging a
reviewed release in an ops-readable path.

The three news shadow LaunchDaemons were subsequently retired by explicit user
decision. Their local artifacts were retained; this evidence paragraph records
the pre-retirement observation rather than current runtime state.

The reviewed release layout is:

- immutable release: `/Users/ops/services/chumji-news-releases/<commit>`
- promoted runtime link: `/Users/ops/services/chumji-news-current`
- transitional rollback checkout: `/Users/ops/services/chumji-ops`

For fresh-food cutover, first point `chumji-news-current` at the validated
release, install the reviewed plist, run one manual job, and compare its
`shadow-status.json` with the pre-cutover output. Roll back by restoring the
previous plist and runtime path if the command exits non-zero, any expected
item is missing, or errors are reported. Do not archive the transitional
checkout until every installed command has migrated independently.
