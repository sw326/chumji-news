# chumji-ops

Private operations repository for the Mac mini services, batch jobs, web
preview, manifests, and runbooks operated under the `ops` account.

## Current Role

This repository is now an active operations source. Production and shadow
components have different cutover states, so do not assume every directory is
live merely because it is present here.

- `services/alert-hub/` is the source for the live disaster alert service.
- `jobs/news/` runs AI-less shadow briefings.
- `jobs/fresh-food/` runs a collection and HTML-generation shadow job.
- `jobs/global-intel/` runs source-health and collection shadow jobs.
- `apps/web/` is deployed to the protected `chumji-ops-preview` Vercel project.
- The legacy news and fresh-food publication paths remain production until a
  separate cutover is approved.

See `docs/operations/current-architecture.md` for the authoritative component
and scheduler map.

## Layout

- `apps/web/` - integrated news, prices, alerts, and operations web UI.
- `services/alert-hub/` - Go source for the live disaster alert service.
- `jobs/news/` - AI-less morning, IT, and trend briefing jobs.
- `jobs/fresh-food/` - Garak Market and KAMIS price collection jobs.
- `jobs/global-intel/` - ACLED, GDELT, and OpenSky collection jobs.
- `deploy/macos/` - macOS deployment notes and templates.
- `manifests/` - example manifests containing SecretRef metadata only.
- `security/` - credential and SecretRef handling rules.
- `docs/operations/` - health, logging, rollback, cutover, and architecture
  documentation.

## Operating Boundaries

- Secrets are stored outside Git and represented here only as SecretRefs.
- Scheduler, service, Telegram, Vercel, and Supabase mutations require explicit
  cutover approval.
- Shadow jobs must not publish to Telegram, Supabase, or Vercel production.
- Runtime data and logs live outside the repository under the `ops` account.
- A checked-in deployment template is not proof that a service is active;
  verify the installed LaunchDaemon and current process state.

## Runtime Paths

- Repository checkout: `/Users/ops/services/chumji-ops`
- Shadow outputs:
  `/Users/ops/Library/Application Support/chumji-ops/shadow`
- Logs: `/Users/ops/Library/Logs/chumji-ops`
- Secret files: `/Users/ops/.config/chumji-ops/secrets`
- Live alert binary: `/Users/ops/services/earthquake-alert`

## Related Standalone Services

Some services are intentionally adjacent to this repository instead of nested
inside it:

- `/Users/ops/services/hoyolab-auto`
- `/Users/ops/services/earthquake-alert`
- Investment Assistant currently at
  `/Users/ops/services/claude-workspace/project/investment-assistant-pack`

The Investment Assistant is a live server dependency. Its target layout is a
standalone service directory such as `/Users/ops/services/investment-assistant`;
moving it requires a separate approved cutover and health validation.
