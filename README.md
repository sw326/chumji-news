# chumji-ops

Private operations repository for Chumji service scaffolding, manifests, and runbooks.

This repository is intentionally non-destructive at this stage. It does not contain imported application code, live LaunchAgents, cron entries, production credentials, or commands that mutate running services.

## Layout

- `apps/web/` - reserved for a future web operations surface.
- `services/alert-hub/` - reserved for a future alert routing service.
- `jobs/news/` - reserved for news collection job definitions.
- `jobs/fresh-food/` - reserved for fresh-food job definitions.
- `jobs/global-intel/` - reserved for global-intel job definitions.
- `deploy/macos/` - macOS deployment notes and templates only.
- `manifests/` - example manifests with secret references, never secret values.
- `security/` - credential and SecretRef handling rules.
- `docs/operations/` - health, logging, job-run, rollback, and cutover conventions.

## Current Status

The repository is a scaffold only. Future imports, service activation, scheduler changes, and production cutovers require explicit approval before any live path is changed.

