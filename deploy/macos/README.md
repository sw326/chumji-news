# macOS Deployment Notes

This directory is for inactive templates and notes only.

Do not copy files from this directory into `~/Library/LaunchAgents`, `/Library/LaunchAgents`, `/Library/LaunchDaemons`, cron, or any live service path without explicit cutover approval.

Expected future template conventions:

- Use labels prefixed with `com.chumji.ops.`.
- Keep program paths inside an approved checkout or release directory.
- Reference secrets by SecretRef lookup only.
- Log to approved paths after retention and redaction rules are defined.

