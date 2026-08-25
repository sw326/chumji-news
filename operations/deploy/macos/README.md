# macOS Deployment Notes

This directory contains the reviewed manifest source for `chumji-ops` jobs and
selected standalone services. Files ending in `.plist` correspond to retained
production LaunchDaemon templates; `.example` files remain inactive examples.

Do not copy, load, unload, or replace files in `~/Library/LaunchAgents`,
`/Library/LaunchAgents`, `/Library/LaunchDaemons`, cron, or any live service
path without explicit cutover approval. A checked-in manifest records approved
state; it does not authorize a runtime mutation.

Manifest conventions:

- Use labels prefixed with `com.chumji.`.
- Keep program paths inside an approved checkout or release directory.
- Reference secrets by SecretRef lookup only.
- Never embed secret values.
- Log only to the component's approved path.

The Investment Assistant keeps its own LaunchDaemon template in its project
repository. The disaster alert hub retains a disabled template because its
production replacement and restart require a separate approval gate.

The consumerless global-intel shadow, public-status exporter, and cathode
market scheduler were retired on 2026-08-25. Their installed plist files are
kept only in the ops-owned retired runtime directory for rollback; active
templates are intentionally absent here.
