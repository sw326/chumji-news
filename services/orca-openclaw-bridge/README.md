# Orca → OpenClaw event bridge

Status: **production cutover approved and installed on 2026-08-14**.

This service keeps execution orchestration on the company Orca runtime while
forwarding sanitized milestones to a personal Mac OpenClaw session. It replaces
interactive SSH polling with blocking Orca waits.

Authoritative lifecycle events are discovered from registered source Run IDs.
The bridge resolves the Run's current coordinator handle before each wait, so a
terminal rebind does not break delivery. A dedicated observer Run remains
available for curated `status` milestones that do not exist as lifecycle mail.

## Safety boundary

- Read registered source Runs only with non-consuming `check --peek --wait`;
  never ACK or mutate their Deliveries.
- Forward source `worker_done`, `escalation`, `question`, and `decision_gate`
  summaries automatically. Forward explicitly useful `status` only through the
  dedicated observer Run.
- Treat every Orca field as untrusted data. The bridge applies bounded secret
  redaction and forwards only selected payload keys.
- Mark an event delivered before acknowledging the whole Orca Delivery.
- Refuse automatic replay when delivery outcome is ambiguous.
- Keep the OpenClaw Gateway loopback-only. The Mac initiates the SSH connection.

Orca returns the entire oldest Delivery even when a type filter merely wakes the
waiter. The bridge therefore accounts for every message in a batch, records
non-allowlisted messages as skipped, and ACKs only after the complete batch is
handled.

The automatic source watcher projects only Run/message correlation,
Task/Dispatch IDs, outcome, phase, subject, and bounded/redacted body. It drops
the source payload's file list and never forges lifecycle mail. Observer copies
are reserved for coordinator-authored, sanitized milestone summaries.

For `question` and `decision_gate` copies, `sourceRunId` is mandatory. A user
response is returned as a high-priority `status` control message to that source
Run; the source coordinator remains the only actor allowed to reply to the
worker or resolve its gate. The observer never impersonates a project
coordinator.

The long-running receiver and response CLI share one state journal. Every
mutation is serialized with an advisory lock and reloads the latest journal
before writing, preventing a stale process from reverting delivery or response
state.

## Local validation

```bash
python3 -m unittest discover -s services/orca-openclaw-bridge/tests -v
python3 -m py_compile services/orca-openclaw-bridge/bridge.py
```

## Prototype execution

Copy `config.example.json` outside the repository, replace every placeholder,
and keep it mode `0600`. Start with a non-delivering test session:

```bash
python3 services/orca-openclaw-bridge/bridge.py \
  --config /path/to/private-config.json \
  --once
```

Use `--dry-run --once` to validate and format one replayed Delivery without
calling OpenClaw or acknowledging Orca. Do not point the prototype at a live
Telegram session until the observer Run, redaction, replay, and failure tests
have passed.

To make a company Run visible to every OpenClaw session, add its durable Run ID
to private config `watched_runs`, validate the config and tests, then restart
the LaunchAgent under an approved operations change. Do not store or target a
coordinator terminal handle: the bridge resolves the current handle from the
Run at runtime.

Return a user response by passing UTF-8 text as base64. The response is carried
to the company side over SSH stdin and is never interpolated into a remote
shell command:

```bash
python3 services/orca-openclaw-bridge/bridge.py \
  --config /path/to/private-config.json \
  --respond-event msg_bridge_event \
  --response-base64 <base64-utf8>
```

Use `--list-pending` to enumerate unanswered `question` and `decision_gate`
events when a Telegram answer arrives outside the dedicated bridge session.
An agent can avoid shell quoting entirely by writing the answer to
`/tmp/orca-openclaw-bridge-response-<event-id>.txt` and using
`--response-file` instead of `--response-base64`.

## Deployment status

Production cutover was explicitly approved on 2026-08-14. The disabled
LaunchAgent template remains documentation only; the live install is managed
from the release and configuration paths recorded in the operations SOT.
Further service, transport, session-target, or polling-path changes require a
new explicit approval.
