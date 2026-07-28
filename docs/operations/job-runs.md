# Job-Run Conventions

Each job should be repeatable, observable, and safe to retry.

## Run Identity

Every run should have a stable `runId` and write one summary record.

Summary fields:

- `job`
- `runId`
- `trigger`
- `startedAt`
- `finishedAt`
- `status`
- `attempt`
- `recordsRead`
- `recordsWritten`
- `errorCategory`

## Retry Behavior

- Retries should be idempotent or guarded by explicit dedupe keys.
- Partial writes should be detectable from the run summary.
- Backfills require a separate plan before touching production data.

