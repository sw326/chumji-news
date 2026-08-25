# AGENTS.md

## Scope

These instructions apply to the entire `chumji-news` repository.

## Repository role

- This repository is the only development source for the news web product and
  the operational jobs and services previously developed in `chumji-ops`.
- Keep the production Next.js application at the repository root.
- Put operational jobs, services, manifests, and runbooks under `operations/`.
- Do not recreate a second web application under `operations/` or another
  repository. New UI work belongs in the root app.

## Operating rules

- Preserve existing dirty worktrees. Do not reset, clean, overwrite, or delete
  user work unless explicitly instructed.
- Never commit secrets, tokens, cookies, `.env` files, private keys, API keys,
  account identifiers, or credential dumps.
- Store only SecretRef metadata in Git. Mutable data and logs remain outside
  the repository.
- Do not change, stop, restart, replace, or reconfigure a live service,
  scheduler, cron, LaunchAgent, LaunchDaemon, Gateway, Vercel project,
  Supabase project, or production path without an approved cutover.
- A checked-in deployment template is not evidence that the component is live.
  Verify the declared architecture and runtime state before a mutation.

## Validation

For web changes, run the smallest relevant tests and normally finish with:

```bash
npm run check
```

For operational changes, run the component-specific Python, Go, or Node tests
documented under `operations/`. Before pushing, verify that Git changes are
intentional and scan new configuration for credential values.

## Knowledge maintenance

The personal wiki is a context layer, not an operations source of truth. For
durable decisions or reusable findings, follow the `maintain-personal-wiki`
skill and link back to this repository's current architecture document rather
than copying mutable runtime state.
