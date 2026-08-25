# Issue 15 Ops UI Validation

Status: completed in isolated branch `sw326/issue-15-ops-ui`.

## Merge Evidence

The branch integrated the verified non-production branches with explicit merge commits:

- `9c03731` - merged `origin/sw326/issue-13-web-preserve`.
- `c3e992e` - merged `origin/sw326/issue-14-alert-shadow`.
- `4e95a83` - merged `origin/sw326/issue-16-batch-plan`.

No merge conflicts occurred.

## Implementation

- Added preview-only `/alerts` and `/operations` App Router screens in `apps/web`.
- Added typed local fixture adapter files under `apps/web/src/lib/ops-preview-*`.
- Added read-only navigation tabs for alerts and operations.
- Added fixture tests for public-status allowlist and read-only runtime controls.
- Documented upload/status API, proposed Supabase schema, privacy allowlist, authentication boundary, preview validation, and rollback in `docs/operations/ops-preview-contracts.md`.

## Validation Results

- `apps/web`: `npm ci` passed; npm reported 8 audit findings in imported dependencies and pending install-script approval warnings for `sharp` and `unrs-resolver`.
- `apps/web`: `npm run test` passed, 2 tests.
- `apps/web`: `npm run lint` passed after a narrow `scripts/*.js` override for preserved CommonJS import scripts from the web import.
- `apps/web`: `npm run build` passed.
- `apps/web`: local dev smoke test returned HTTP 200 for `/operations` and `/alerts?severity=high`; the dev server was stopped.
- `services/alert-hub`: `go test ./...` passed.
- `services/alert-hub`: `go build -trimpath -o /tmp/chumji-alert-hub-shadow/earthquake-alert .` passed.
- `services/alert-hub`: `/tmp/chumji-alert-hub-shadow/earthquake-alert -config config.shadow.example.json -dry-run -fixture testdata/event.json` passed with exit code 0.
- Repository root: `scripts/validate-batch-contracts.sh` passed.
- Secret scan: high-signal token/key/private-key regex scan returned no matches; assignment-pattern scan returned only code variable/header assignments, not committed credential values.

## Remaining Approval Gates

Explicit approval is still required before any production Supabase/Vercel connection, preview persistence setup, scheduler or LaunchAgent/LaunchDaemon changes, production credential use, shadow run against production data, public deployment, cutover, rollback, or traffic migration.
