# Public Ops Status Exporter

This job reads the alert hub's SQLite history and health JSON in read-only mode,
then emits a redacted `ops-public-status/v1` document.

It never reads Telegram credentials, sends alerts, or controls services.
`--upload` performs the core two-row upsert only when an ops-owned Supabase
SecretRef is supplied. When the validated cathode market-board artifact exists,
the exporter also upserts the read-only `trade-market` snapshot after migration
004 is applied. The checked-in LaunchDaemon definition remains uninstalled until
migration `003_create_ops_public_snapshots.sql` has been applied.
