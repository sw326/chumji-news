# Public Ops Status Exporter

This job reads the alert hub's SQLite history and health JSON in read-only mode,
then emits a redacted `ops-public-status/v1` document.

It never reads Telegram credentials, sends alerts, controls services, or writes
to Supabase by itself. Applying the Supabase migration and enabling an uploader
require a separate cutover approval.
