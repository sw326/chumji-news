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

The primary navigation exposes only `news`, `it`, `trend`, and `opendata`.
Historical categories with stored rows remain in the category type and complete
category list so old detail URLs, database rows, and bookmark filters continue
to work. `moltbook` is removed from the application contract because it has no
rows and no producer. Applied migration history is not rewritten and no
historical content is deleted.

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

## Production-to-operations gap

The existing `operations/jobs/news` implementation is a shadow candidate, not
a drop-in copy of the active publisher:

| Concern | Active OpenClaw jobs | `operations/jobs/news` |
| --- | --- | --- |
| Profiles | news, IT, trend | news, IT, trend |
| Collection | workspace-specific fetchers; trend has observed-evidence ranking | standalone public RSS/Atom fetcher |
| Interpretation | OpenClaw GPT summarizer | deterministic AI-less ranking and rendering |
| Supabase publication | enabled | deliberately absent |
| Telegram publication | enabled | deliberately absent |
| Runtime | `claude-workspace/scripts/cron` | `chumji-news/operations/jobs/news` shadow |

Moving the scheduler path now would remove interpretation and both publication
outputs, and would change source-selection behavior. Readiness therefore needs
fixture comparisons for each active profile, an explicit decision on AI-less
versus model-assisted summaries, and separately reviewed Supabase and Telegram
adapters. The dormant Reddit script is not part of this migration baseline.
