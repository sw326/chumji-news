# Ops Preview Contracts

Status: proposal only for `sw326/openclaw_v2#15`. Nothing in this document has been applied to production Supabase, Vercel, launchd, cron, or any live service path.

## Upload API Proposal

Preview writers may eventually upload alert and runtime status records through an authenticated preview API:

- `POST /api/ops-preview/alerts`: accepts normalized public alert metadata and timeline events.
- `POST /api/ops-preview/status`: accepts declared service/job status records from a safe public-status schema.
- `GET /alerts` and `GET /operations`: read-only UI routes; no mutation actions.

Required request boundaries:

- Authentication: preview service role or signed machine token scoped to `ops-preview:write`, stored only as `SecretRef` metadata until approval.
- Authorization: production service roles, delivery tokens, Telegram credentials, scheduler credentials, and live Supabase project credentials are not accepted.
- Idempotency: uploads must include `source`, `source_event_id`, `observed_at`, and `runtime_id` or equivalent duplicate key.
- Rejection: payloads containing secret-looking field names or values must be rejected before persistence.

## Supabase Schema Proposal

The proposed tables are inactive and must be created only in an approved preview Supabase project:

```sql
-- proposal only; not applied to production
create table ops_preview_alerts (
  id text primary key,
  category text not null,
  severity text not null,
  status text not null,
  title text not null,
  source text not null,
  region text not null,
  observed_at timestamptz not null,
  updated_at timestamptz not null,
  public_summary text not null,
  privacy_class text not null check (privacy_class = 'public-status')
);

create table ops_preview_alert_timeline (
  alert_id text not null references ops_preview_alerts(id) on delete cascade,
  at timestamptz not null,
  actor text not null,
  title text not null,
  note text not null,
  status text,
  primary key (alert_id, at, title)
);

create table ops_preview_runtime_status (
  id text primary key,
  kind text not null check (kind in ('service', 'job')),
  name text not null,
  owner text not null,
  declared_in text not null,
  schedule text not null,
  last_run_at timestamptz,
  next_expected_at timestamptz,
  freshness_minutes integer,
  status text not null,
  failure_state text not null,
  public_summary text not null,
  control_policy text not null check (control_policy = 'read-only-preview'),
  generated_at timestamptz not null
);
```

## Privacy Allowlist

Only these fields may be rendered by `/alerts` and `/operations`:

- Alert fields: `id`, `category`, `severity`, `status`, `title`, `source`, `region`, `observedAt`, `updatedAt`, `publicSummary`, `privacyClass`, and timeline `at`, `actor`, `title`, `note`, `status`.
- Runtime fields: `id`, `kind`, `name`, `owner`, `declaredIn`, `schedule`, `lastRunAt`, `nextExpectedAt`, `freshnessMinutes`, `status`, `failureState`, `publicSummary`, `controlPolicy`, and check `name`, `status`, `observedAt`, `summary`.
- Explicitly disallowed: token values, cookie values, headers, private URLs, raw payload dumps, chat IDs, credential paths beyond approved SecretRef names, operator names, user identifiers, and control endpoints.

## Preview Validation

Before any preview persistence is approved:

- `npm ci`, `npm run test`, `npm run lint`, and `npm run build` must pass in `apps/web`.
- `scripts/validate-batch-contracts.sh` must pass from the repository root.
- `go test ./...`, `go build`, and dry-run fixture execution must pass in `services/alert-hub`.
- Secret-pattern scans must show no committed credential values.
- Manual review must verify `/alerts` filters and detail timeline, and `/operations` exposes no start/stop/retry/control buttons.

## Rollback

Rollback for this issue is limited to removing the preview routes, local fixtures, tests, and this proposal. No production rollback exists because no production service, scheduler, database, deployment, token, or traffic path is changed by this work.
