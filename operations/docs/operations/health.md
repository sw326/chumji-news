# Health Conventions

Services should expose a lightweight health check before they are considered deployable.

## Service Health

- `GET /healthz` returns process liveness and dependency readiness.
- `GET /readyz` may be added when readiness differs from liveness.
- Responses must avoid secrets, user data, raw upstream payloads, and credential metadata.
- A failing dependency should be named by category, not by secret or token.

## Job Health

Jobs should write a last-success marker after completing all required work.

Recommended marker fields:

- `job`
- `startedAt`
- `finishedAt`
- `status`
- `inputWindow`
- `recordsProcessed`
- `errorCategory`
