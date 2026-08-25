# Alert Hub Shadow Import

This directory is an inactive shadow copy of the current `earthquake-alert` Go service for GitHub issue `sw326/openclaw_v2#14`.

No file in this directory is loaded by launchd, installed into a live path, or wired to production delivery. The deployed runtime remains outside this repository at `/Users/ops/services/earthquake-alert` under launchd label `com.chumji.earthquake-alert`.

## Provenance

- Source path: `/Users/chumji/.openclaw/workspace/projects/earthquake-alert`
- Source git root: `/Users/chumji/.openclaw/workspace`
- Source commit at import: `ab7a75d65add9f12fe03ddd94168200e3404bc2a`
- Import date: `2026-07-29`
- Imported content: Go source, Go tests, `go.mod`, `go.sum`, `testdata/event.json`, and disabled deployment templates.
- Source worktree state at import: dirty at the OpenClaw workspace root; dirty files were preserved in place and were not reset, cleaned, or modified.

## Safety Boundary

- Do not run this service without `-dry-run` during shadow validation.
- Do not use `-test-notification` from this repository without explicit production-credential approval.
- Do not install, load, unload, bootout, restart, kill, rename, or replace `com.chumji.earthquake-alert`.
- Do not copy files from this directory into `/Users/ops/services/earthquake-alert` or `/Users/ops/.config/earthquake-alert` without cutover approval.
- Do not run a second live consumer against the EMSC websocket or Telegram delivery path.

## Earthquake source redundancy

The shadow source combines two deterministic earthquake paths:

- EMSC near-real-time WebSocket messages remain the push source.
- The official USGS `M4.5+ past hour` GeoJSON summary is conditionally polled once per minute, matching the feed's published update cadence.

The first actionable source creates the alert. A later report is associated with the same earthquake only when its origin time is within 30 seconds, epicenter is within 100 km, and magnitude differs by no more than 1.5. Cross-source reports that do not materially change magnitude, urgency tier, depth, or epicenter are recorded without sending a duplicate Telegram alert. Startup establishes a USGS baseline without replaying historical events.

Routine source revisions are stored for deduplication but do not send Telegram messages. Earthquake revisions notify only when they cross the urgent-magnitude threshold, move into a more Korea-relevant tier, or increase magnitude by at least 0.5. PTWC and GDACS notify new, escalated, and resolved events while suppressing same-level bulletin updates; unclassified NOAA SWPC updates are also suppressed. This keeps the live channel focused on first reports and materially more urgent changes.

## Isolated Validation

Run from `services/alert-hub`:

```bash
go test ./...
go build -trimpath -o /tmp/chumji-alert-hub-shadow/earthquake-alert .
./earthquake-alert -config config.shadow.example.json -dry-run -fixture testdata/event.json
```

The fixture command processes one local EMSC fixture and exits without reading the Telegram token file or sending Telegram messages.

## SecretRefs

Secret values are not stored in this repository. Use names only:

- `alert-hub.telegram-token` - provider: local file credential; lookup path name: `/Users/ops/.config/earthquake-alert/telegram-token`
- `alert-hub.telegram-chat-id` - provider: deployment config; lookup path name: `/Users/ops/.config/earthquake-alert/config.json`
- `alert-hub.launchdaemon-config` - provider: macOS launchd template; lookup path name: `com.chumji.earthquake-alert`

See [`operations/security/SecretRef.md`](../../security/SecretRef.md) for repository rules.

## Files

- Go module: `*.go`, `*_test.go`, `go.mod`, `go.sum`
- Local fixture: `testdata/event.json`
- Dry-run config template: `config.shadow.example.json`
- Disabled launchd template: `deploy/com.chumji.earthquake-alert.plist.template.disabled`
- Cutover runbook: `docs/cutover-runbook.md`
- Source history notes: `docs/source-history.md`
