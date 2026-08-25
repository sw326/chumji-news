# Secret Handoff

Generic remote secret-entry broker for OpenClaw workflows. This directory is the source and test SOT; live deployment state and rollback procedures are recorded in `docs/operations/current-architecture.md` and `docs/operations/secret-handoff.md`.

## Contract

1. A trusted local coordinator creates a short-lived request with a field schema.
2. Telegram receives only the one-time HTTPS entry URL and non-secret scope metadata.
3. The browser exchanges the URL token for an `HttpOnly`, `SameSite=Strict`, `Secure` cookie and is redirected to a token-free URL.
4. The form encrypts all submitted fields with AES-256-GCM and stores them in SQLite.
5. The status API returns field-level exec `SecretRef` metadata, never cleartext.
6. The local resolver supplies only explicitly requested fields to the runtime. There is no HTTP reveal endpoint.

For owner-bound requests, set `ownerVerification` to `telegram_dm_code`. The service sends an eight-digit challenge directly to the owner DM through the configured Telegram bot. The request API and group task card never receive that code.

Supported schemas include a single key, username/password, and up to ten mixed fields. Every field is encrypted regardless of its display kind.

```json
{
  "ownerId": "telegram:OWNER_ID",
  "requesterAgent": "fin",
  "purpose": "API credentials",
  "allowedDomains": ["api.example.com"],
  "retention": "persistent",
  "ownerVerification": "telegram_dm_code",
  "ttlSeconds": 900,
  "schema": {
    "fields": [
      {"name": "username", "label": "Username", "kind": "username"},
      {"name": "password", "label": "Password", "kind": "password"}
    ]
  }
}
```

Field kinds are `secret`, `token`, `username`, `password`, and `text`. Retention is `persistent`, `session`, or `one_time`. Session retention also requires `secretTtlSeconds`.

## Internal API

The API must remain behind loopback or a private service boundary. It uses a bearer token loaded from the configured strict file or environment input.

- `POST /api/v1/requests`
- `GET /api/v1/requests/:id/status`
- `POST /api/v1/requests/:id/cancel`
- `POST /api/v1/credentials/:id/revoke`

The only public routes are `GET /enter?token=...`, `GET /enter`, and `POST /enter`.

The create response includes a channel-neutral `controlCard` projection with a URL action for `보안 입력` and a callback descriptor for cancellation. Telegram remains a display/input adapter; the broker request remains the status source of truth.

## Resolver

The resolver implements the OpenClaw exec SecretRef JSON protocol on stdin/stdout.

```sh
node src/main.mjs resolve --config /path/to/config.json
```

Input:

```json
{"protocolVersion":1,"provider":"secret-handoff","ids":["cred_OPAQUE/username","cred_OPAQUE/password"]}
```

One-time credentials must request all required fields in the same resolver call because the credential is consumed as a bundle.

`openclaw.provider.example.json5` shows the provider shape for the current split-user architecture. Because the Gateway runs as `chumji` while the vault is owned by `ops`, deployment needs a narrowly scoped, exact-argv sudoers rule for only this resolver invocation. Do not grant generic `node`, shell, database, or service-account access. SecretRef reduces configuration and model exposure; it is not an OS process-isolation boundary.

## Runtime security

- Master key: macOS Keychain by default; a strict `0600` external key file is supported for isolated deployments.
- The control token and Telegram challenge bot token may also be loaded from strict service-user-owned `0600` files. Environment-variable inputs remain supported for development compatibility.
- Control token and master key are never stored in this repository.
- Request tokens are stored only as SHA-256 hashes and become unusable after the first exchange.
- Form sessions use an HttpOnly cookie and HMAC-bound CSRF token.
- Optional owner verification is delivered out-of-band to the owner Telegram DM and is HMAC-protected in storage.
- Token exchanges and form submissions are rate-limited in memory; a trusted reverse proxy may supply the client address only when `trustProxy` is enabled.
- Responses use `no-store`, no-referrer, CSP, frame denial, and MIME sniffing protection.
- Audit rows contain event type, opaque IDs, result, and time only.
- No request body or secret value should be logged by the service or reverse proxy.

The reverse proxy must expose only `/enter`, never `/api/v1/*`. Keep `secureCookie: true` and bind the app to loopback. Any ingress, owner-authentication, or lifecycle change remains a separately reviewed operations change even when the service is already deployed.

The reviewed macOS manifest is `deploy/macos/com.chumji.secret-handoff.plist`. Install a commit-addressed release and keep mutable configuration, the encrypted vault, and all secret inputs under `/Users/ops/Library/Application Support/secret-handoff`. See `docs/operations/secret-handoff.md` for the cutover and rollback checks.

## Test

```sh
cd services/secret-handoff
npm test
```
