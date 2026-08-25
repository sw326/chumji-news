# News category and source audit

Status: review  
Observed: 2026-08-25

This audit separates currently published feeds from historical categories. It
does not delete Supabase rows, change a scheduler, or migrate a runtime path.

## Findings

| Category | Rows | Latest post | Verified producer | Product status |
| --- | ---: | --- | --- | --- |
| `news` | 155 | 2026-08-25 | OpenClaw morning-news cron | active |
| `it` | 158 | 2026-08-25 | OpenClaw IT cron | active |
| `trend` | 154 | 2026-08-24 | OpenClaw trend cron | active |
| `opendata` | 47 | 2026-08-25 | fresh-food snapshot cron | active |
| `reddit` | 70 | 2026-06-29 | script remains, no installed cron found | historical |
| `issues` | 8 | 2026-04-07 | no installed producer found | historical |
| `realestate` | 3 | 2026-04-06 | no installed producer found | historical |
| `system` | 19 | 2026-04-05 | no installed producer found | historical |
| `moltbook` | 0 | never | no producer found | never launched |

The issue digest contains explicit links to `sw326/openclaw-workspace`. That
repository is not archived, but its last push was 2026-04-05; the active
workspace repository is `sw326/claude-workspace`. The renderer also converted
every bare `#123` into an `openclaw-workspace` issue link without knowing the
owning repository. That implicit conversion was removed. Existing explicit
historical links remain untouched.

## Product boundary

The application contract and primary navigation expose only `news`, `it`,
`trend`, and `opendata`. Retired categories are also filtered from aggregate
post and bookmark queries, and their direct detail routes are rejected as
invalid categories. Applied migration history is not rewritten and this change
does not delete stored Supabase rows. Database deletion requires a separately
reviewed target count and rollback decision.

The obsolete root `TODOS.md` and unused `src/lib/mock-data.ts` were removed.
The TODO described already-completed category and UI work and incorrectly
claimed a live real-estate cron; the mock data had no imports.

## Preparation for operations migration

Before moving a producer into this repository, record for each feed:

1. source ownership and current source health;
2. installed scheduler and last successful run;
3. output category and database contract;
4. secrets as references only;
5. shadow comparison, cutover, and rollback evidence.

Do not revive the Reddit, issue, real-estate, system, or Moltbook categories by
copying old scripts. A future feed needs an explicit product decision and a
fresh source audit. The active OpenClaw jobs remain the production path until a
separately approved component-by-component cutover to `operations/`.

## Rejected AI-less shadow

The former `operations/jobs/news` implementation was not a drop-in copy of the
active publisher:

| Concern | Active OpenClaw jobs | Rejected shadow |
| --- | --- | --- |
| Profiles | news, IT, trend | news, IT, trend |
| Collection | workspace-specific fetchers; trend has observed-evidence ranking | standalone public RSS/Atom fetcher |
| Interpretation | OpenClaw GPT summarizer | deterministic AI-less ranking and rendering |
| Supabase publication | enabled | deliberately absent |
| Telegram publication | enabled | deliberately absent |
| Runtime | `claude-workspace/scripts/cron` | retired local-only LaunchDaemons |

The same-day sample below showed insufficient parity, so the user chose to
retire this implementation rather than optimize a second producer. Its code,
contracts, manifests, and three installed LaunchDaemons were removed. Git
history and existing local artifacts remain available as evidence. The active
production jobs are unchanged and the dormant Reddit script is not part of a
future migration baseline.

### Same-day URL parity sample

An exact-release shadow rerun and the rendered production pages were compared
on 2026-08-25 using canonical cited article URLs. This is a timing-sensitive
sample, not a general quality score:

| Profile | Shadow URLs | Production URLs | Overlap | Shadow overlap | Production overlap |
| --- | ---: | ---: | ---: | ---: | ---: |
| morning | 14 | 13 | 2 | 14.29% | 15.38% |
| IT | 8 | 9 | 1 | 12.50% | 11.11% |
| trend | 18 | 0 | 0 | 0% | not applicable |

The trend page existed but contained no cited articles at the observation
time, before its normal production publication window. Morning and IT used the
same named source families, yet their low overlap shows that feed timing,
per-source limits, title filters, and selection policy materially change the
briefing before model interpretation is considered.

Any future consolidation uses this order:

1. preserve production collection and evidence-based trend selection in this
   repository as the baseline;
2. decide separately whether article summaries remain model-assisted;
3. only then add idempotent Supabase and Telegram publication adapters.

Do not recreate the rejected shadow under another path.
