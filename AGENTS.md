# AGENTS.md

## Scope

These instructions apply to the entire `chumji-ops` repository.

## Operating Rules

- Preserve existing dirty worktrees. Do not reset, clean, checkout over, or delete user work unless explicitly instructed.
- Do not import existing application code until a separate approval names the source and destination.
- Do not change, stop, restart, replace, or reconfigure any existing service, scheduler, cron, LaunchAgent, LaunchDaemon, tmux session, gateway, Vercel project, Supabase project, or live path.
- Keep manifests and deployment files as examples until cutover approval is recorded.
- Never commit secrets, tokens, cookies, `.env` files, private keys, API keys, or credential dumps.
- Use `security/SecretRef.md` for secret references. Store only provider, scope, owner, and lookup path metadata.
- Prefer additive documentation and templates. If a future change could affect production, stop and request approval.

## Approval Boundaries

Explicit approval is required before:

- Installing or loading a LaunchAgent or LaunchDaemon.
- Editing cron, systemd, nginx, shell rc files, gateway configs, or production project settings.
- Writing into a live service path outside this repository.
- Rotating, copying, or reading secret values.
- Running a job against production credentials or production data.
- Performing cutover, rollback, or traffic migration.

## Validation Expectations

Before pushing changes, validate:

- Git status is limited to intentional files.
- Secret-pattern scan does not report committed credential values.
- Example manifests contain only SecretRef names or placeholder references.
- Documentation clearly marks templates as inactive until approved.

