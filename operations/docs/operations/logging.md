# Logging Conventions

Logs should make operations debuggable without leaking private data.

## Required Fields

- `timestamp`
- `level`
- `component`
- `event`
- `requestId` or `runId` when available

## Redaction

Never log:

- Tokens, passwords, cookies, private keys, or API keys.
- Full request or response bodies from credentialed services.
- User private data unless a future runbook explicitly approves a narrowed field.

## Retention

Retention is not configured by this scaffold. Any future retention policy must be approved before changing live log paths or schedulers.
