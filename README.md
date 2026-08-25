# chumji-news

`chumji-news` is the single development repository for the personal news web
product and the Mac mini jobs and services that support it.

The Next.js production application remains at the repository root so the
existing `chumji-news` Vercel project and local publication workflow do not
need a root-directory change. Operational source imported from the retired
`chumji-ops` repository lives under `operations/`.

## Layout

- `src/`, `public/`, `supabase/`, and root `scripts/` — production news,
  fresh-food, and scraps web application.
- `operations/jobs/` — deterministic and shadow batch jobs.
- `operations/services/` — alert hub, Orca bridge, and secret-handoff source.
- `operations/deploy/` — inactive or reviewed macOS deployment definitions.
- `operations/docs/` — architecture, health, cutover, and rollback records.
- `operations/security/` — SecretRef contract. Secret values never belong in
  Git.

The abandoned `chumji-ops/apps/web` fork is intentionally absent from the
working tree. Its Git history is retained through the repository-consolidation
merge, but future UI development happens only in the root Next.js app.

## Web development

```bash
npm ci
npm run check
npm run verify:production
```

`verify:production` is read-only. Do not deploy or change Supabase while
running repository validation.

## Operations development

Each component has its own README or contract under `operations/`. Run tests
from the component directory or use the documented module-specific command.
There is not yet one root command for every Python, Go, and Node component.

Repository consolidation does not itself move a scheduler, service, runtime
checkout, Vercel project, Supabase project, or credential. Read
`operations/docs/operations/current-architecture.md` and verify live state
before any operational mutation.

## Safety

- Preserve dirty worktrees and generated snapshots.
- Keep secrets and mutable runtime data outside Git.
- Treat deployment definitions as source, not proof that a service is active.
- Require a reviewed cutover before changing cron, launchd, Vercel, Supabase,
  Telegram, Gateway, or an ops-owned live path.
