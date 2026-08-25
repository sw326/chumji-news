# Secret Handoff Operations

This runbook covers the generic remote credential-entry broker. The service is
owned by `ops`, binds only to `127.0.0.1:8789`, and exposes only `/enter` through
the existing Tailscale HTTPS frontend. Control APIs remain loopback-only.

## Runtime boundary

- Immutable releases: `/Users/ops/services/secret-handoff/releases/<commit>`
- Active symlink: `/Users/ops/services/secret-handoff/current`
- Mutable state: `/Users/ops/Library/Application Support/secret-handoff`
- Logs: `/Users/ops/Library/Logs/secret-handoff`
- LaunchDaemon: `com.chumji.secret-handoff`
- Public form path: `https://chumji-macmini.tailcfd4f8.ts.net/enter`

The reverse proxy must route only `/enter` to `127.0.0.1:8789`. Never add a root
handler or an `/api` handler. Request creation, status, cancellation, revocation,
and credential resolution stay on the Mac mini.

## Required private files

All files below are regular, non-symlink files owned by `ops` with mode `0600`:

- `config.json`
- `master-key` containing exactly 32 random bytes encoded as base64
- `control-token` containing a high-entropy random bearer token
- `telegram-bot-token` used only to send owner verification challenges

Do not print, log, commit, or copy their contents into another service config.
The Telegram token may be provisioned byte-for-byte from an approved existing
SecretRef without reading it into an agent response.

## Cutover checks

1. Run `npm test` from the candidate release.
2. Validate the plist with `plutil -lint` and the private config with `jq -e`.
3. Confirm port `8789` is unused and save `tailscale serve status --json` before
   mutation. The installed legacy node configuration is not exported by the
   newer service-oriented `serve get-config --all` command.
4. Install the LaunchDaemon and verify it is running as `ops` and listening only
   on loopback.
5. Add the exact `/enter` path handler with backend target
   `http://127.0.0.1:8789/enter`; a target without the trailing `/enter` strips
   the prefix and returns the wrong route. Re-enable Funnel on port 443 after a
   `serve` mutation and verify both the existing root handler and `/enter` plus
   `AllowFunnel` in `tailscale serve status --json`.
6. Verify external `/enter` returns the no-session error with security headers;
   verify external `/api/v1/requests` still reaches the existing root service or
   returns a non-broker response.
7. Create one short-lived owner-verified test request, open it once, submit dummy
   values, resolve them locally, then revoke the test credential.
8. Add the exact-argv OpenClaw exec provider only after the local resolver and
   sudoers rule pass a dry preflight.

## Rollback

1. Remove only the `/enter` Tailscale handler with the installed client's
   path-scoped form and compare against the saved status snapshot. Never use a
   port-wide `serve --https=443 off`, which also removes the Investment
   Assistant root handler.
2. Boot out `com.chumji.secret-handoff` and remove its installed plist.
3. Restore the prior `current` symlink if this was an upgrade.
4. Keep the encrypted database and key material for diagnosis unless explicit
   credential destruction is approved. Revoke created credentials before reuse.

Rollback must not reset the whole Tailscale Serve configuration or disturb the
Investment Assistant root handler.
