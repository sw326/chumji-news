# Chumji News Web Import

## Scope

`apps/web/` was imported from `/Users/chumji/workspace/chumji-news` for GitHub issue `sw326/openclaw_v2#13`.

This import is review and preview only. It does not change the production URL, Vercel project, Supabase project, schedulers, LaunchAgents, LaunchDaemons, gateways, cron entries, or any live service path.

## Provenance

- Source checkout: `/Users/chumji/workspace/chumji-news`
- Source remote: `https://github.com/sw326/chumji-news.git`
- Source branch: `main`
- Source committed HEAD at import: `a90a2d941aece87c7d7df9c238b1ceec6bc9a70f`
- Destination prefix: `apps/web/`
- Import method: local Git remote plus `git subtree add --prefix=apps/web chumji-news-src/main`

The subtree merge preserves the committed source history in this repository. Current source worktree changes were then applied as a separate overlay commit so committed history and dirty work preservation remain auditable.

## Source Worktree Preservation

Source status observed before import:

```text
## main...origin/main
 M src/components/NewsBoardClient.tsx
 M src/lib/data.ts
 M src/lib/types.ts
?? public/
?? scripts/save-price-snapshot.js
?? src/app/prices/
?? src/components/MainTabs.tsx
```

The source checkout was not modified. The tracked dirty diff was applied under `apps/web/`, and untracked non-ignored files were copied under `apps/web/` using the source Git untracked file list.

Ignored local files were intentionally not imported. This excludes `.env.local`, `.vercel/`, build output, dependency directories, and other ignored local state.

## Deployment And Secret Audit

The source checkout had `.vercel/project.json` present, with project and org identifiers present. That local Vercel linkage was not imported.

No `vercel.json` was found in the source checkout during the audit. `apps/web/` has no imported `.vercel/` directory.

Environment variable names observed without reading secret values:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`

`apps/web/.env.local.example` contains placeholder values only. Real secret values must remain outside Git and should be referenced through `security/SecretRef.md` metadata if deployment work is approved later.

## Preview-Only Validation

Allowed local validation:

```bash
cd apps/web
npm run lint
npm run build
```

Do not run commands that deploy, link Vercel, mutate Supabase, load schedulers, or write to live service paths. Supabase migrations under `apps/web/supabase/` are imported source artifacts only and must not be applied to production without an explicit cutover approval.

## Rollback

Before merge, rollback is deleting this feature branch or reverting its import commits.

After merge, rollback should use normal Git revert of the import commits. Do not delete or reconfigure Vercel projects, Supabase projects, schedulers, or live service paths as part of rollback unless a separate approval explicitly authorizes that operational change.
