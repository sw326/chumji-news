# Alert Hub Cutover Runbook

Status: production cutover completed for revision `39819a8` on 2026-08-16. Any
future cutover still requires a new explicit approval.

## Deployment Record

- Revision: `39819a898c6c65e67295730bb08ebf525322884f`.
- Runtime: `/Users/ops/services/earthquake-alert`.
- Launchd label: `com.chumji.earthquake-alert`.
- Change: routine earthquake, PTWC, GDACS, and unclassified SWPC revisions are
  stored without Telegram delivery; new, escalated, and resolved events remain
  actionable.
- Binary SHA-256:
  `98144e5d60ad10e0b0a49e3fd17bc62355b3150ddd7941af5d986beaf0dd92c9`.
- Validation: LaunchDaemon returned to `running` as `ops` with exit code 0;
  EMSC connected and received a post-restart message; USGS polls advanced at
  22:15, 22:16, and 22:17 KST; all source error fields were empty.
- Rollback snapshot:
  `/Users/ops/services/earthquake-alert.rollback-20260816-221600` with prior
  binary SHA-256
  `9bfdcf0f84963490da8fbee1b692a714c39a9ce2fda1a1355d62912f61e6d24a`.

## Approval Gate

Stop until a human records explicit approval naming:

- Source revision to deploy.
- Destination runtime path.
- launchd label.
- SecretRef names to resolve.
- Cutover window.
- Rollback owner.

For the next deployment, require approval to replace the current
`/Users/ops/services/earthquake-alert` runtime and load or restart
`com.chumji.earthquake-alert` using approved production credentials.

## Pre-Cutover Validation

Run only in this repository before requesting approval:

```bash
cd services/alert-hub
go test ./...
go build -trimpath -o /tmp/chumji-alert-hub-shadow/earthquake-alert .
./earthquake-alert -config config.shadow.example.json -dry-run -fixture testdata/event.json
plutil -lint deploy/com.chumji.earthquake-alert.plist.template.disabled
```

Confirm:

- Git status contains only approved files.
- Secret scan reports no credential values.
- The template plist remains inactive and is not installed.
- The fixture run uses `-dry-run`.
- The production config candidate enables the official USGS `4.5_hour.geojson` feed at a one-minute interval.
- State migration and USGS baseline tests pass without replaying historical earthquakes.
- Cross-source tests cover EMSC-first, USGS-first, material updates, and stale-source regression suppression.

## Cutover Plan

These commands are placeholders and must not be run until the approval gate is satisfied.

1. Record current live binary checksum, config checksum, launchd state, and health file timestamp.
2. Build the approved revision in a temporary staging directory.
3. Resolve `alert-hub.telegram-token` and `alert-hub.telegram-chat-id` using the approved production secret process.
4. Stage the new binary and config outside the live runtime path.
5. Stop the existing service only inside the approved cutover window.
6. Atomically swap the staged runtime into the approved destination.
7. Load or restart only the approved launchd label.
8. Verify `last_usgs_poll_at`, EMSC WebSocket health, logs, and one explicitly approved test notification if requested.
9. Confirm the first USGS poll establishes a baseline and sends no historical Telegram alerts.

## Rollback Plan

If validation fails after approved cutover:

1. Stop only the approved launchd label.
2. Restore the recorded previous runtime directory and config.
3. Reload or restart only the approved launchd label.
4. Confirm health and logs return to the previous known-good behavior.
5. Record the failure, restored revision, timestamps, and operator.

## Prohibited During Shadow Prep

- No `launchctl bootout`, `launchctl bootstrap`, `launchctl kickstart`, or service restarts.
- No live path writes under `/Users/ops/services/earthquake-alert`.
- No production token reads or copies.
- No second live websocket consumer.
- No Telegram sends.
