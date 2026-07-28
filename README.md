# chumji-ops

Private operations repository for Chumji service scaffolding, manifests, and runbooks.

This repository is intentionally non-destructive at this stage. It does not contain live LaunchAgents, cron entries, production credentials, or commands that mutate running services.

## Layout

- `apps/web/` - imported Chumji News web app, preserved from `sw326/chumji-news`.
- `services/alert-hub/` - reserved for a future alert routing service.
- `jobs/news/` - reserved for news collection job definitions.
- `jobs/fresh-food/` - reserved for fresh-food job definitions.
- `jobs/global-intel/` - reserved for global-intel job definitions.
- `deploy/macos/` - macOS deployment notes and templates only.
- `manifests/` - example manifests with secret references, never secret values.
- `security/` - credential and SecretRef handling rules.
- `docs/operations/` - health, logging, job-run, rollback, and cutover conventions.

## Current Status

This repository is still non-production. `apps/web/` contains a preserved import of the Chumji News app for review and preview-only validation; service activation, scheduler changes, deployment linkage, and production cutovers still require explicit approval before any live path is changed.
