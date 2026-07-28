# Alert Hub Source History

## Import Snapshot

- Imported for: GitHub issue `sw326/openclaw_v2#14`
- Import mode: shadow preparation only
- Imported from: `/Users/chumji/.openclaw/workspace/projects/earthquake-alert`
- Source git root: `/Users/chumji/.openclaw/workspace`
- Source commit: `ab7a75d65add9f12fe03ddd94168200e3404bc2a`
- Deployed runtime named by issue: `/Users/ops/services/earthquake-alert`
- Launchd label named by issue: `com.chumji.earthquake-alert`

## Source Worktree State

The source project lives inside a dirty OpenClaw workspace. The dirty workspace was left untouched.

Dirty source-root status recorded at import:

```text
 M AGENTS.md
 M PRINCIPLES.md
 M TOOLS.md
 M cron-migration-plan.md
 M knowledge/README.md
 M knowledge/infra/tools.md
 M knowledge/projects/projects.md
?? archive/crontab-before-openclaw-weather-20260614.txt
?? artifacts/
?? audit-openclaw-runtime-issue11-20260728.md
?? docs/
?? knowledge/infra/gateway-supervision-pattern.md
?? knowledge/projects/company-context.md
?? media/
?? memory/
?? openclaw-workspace-state.json
?? outputs/
?? projects/investment-assistant-pack/
?? skills/
?? tmp/
```

## Runtime Notes

The live runtime path was not modified. This repository only records its name for future approval and cutover planning.

Known operational paths by name:

- Runtime directory: `/Users/ops/services/earthquake-alert`
- Config directory: `/Users/ops/.config/earthquake-alert`
- Token SecretRef name: `alert-hub.telegram-token`
- State and health directory: `/Users/ops/Library/Application Support/EarthquakeAlert`
- History database name: `/Users/ops/Library/Application Support/EarthquakeAlert/history.sqlite3`
- Logs directory: `/Users/ops/Library/Logs/EarthquakeAlert`
- launchd label: `com.chumji.earthquake-alert`
