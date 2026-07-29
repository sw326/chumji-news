# Public Ops Status Exporter

This job reads the alert hub's SQLite history and health JSON in read-only mode,
then emits a redacted `ops-public-status/v1` document.

It never reads Telegram credentials, sends alerts, or controls services.
`--upload` performs a two-row upsert only when an ops-owned Supabase SecretRef
is supplied. The checked-in LaunchDaemon definition remains uninstalled until
migration `003_create_ops_public_snapshots.sql` has been applied.
