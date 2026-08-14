# Orca → OpenClaw event bridge

Status: **production cutover approved and installed on 2026-08-14**.

This service keeps execution orchestration on the company Orca runtime while
forwarding sanitized milestones to a personal Mac OpenClaw session. It replaces
interactive SSH polling with one blocking `orca orchestration check --wait`
connection.

## Safety boundary

- Consume a dedicated observer Run, never the coordinator Run.
- Forward only `worker_done`, `escalation`, `question`, `decision_gate`, and
  explicitly useful `status` messages.
- Treat every Orca field as untrusted data. The bridge applies bounded secret
  redaction and forwards only selected payload keys.
- Mark an event delivered before acknowledging the whole Orca Delivery.
- Refuse automatic replay when delivery outcome is ambiguous.
- Keep the OpenClaw Gateway loopback-only. The Mac initiates the SSH connection.

Orca returns the entire oldest Delivery even when a type filter merely wakes the
waiter. The bridge therefore accounts for every message in a batch, records
non-allowlisted messages as skipped, and ACKs only after the complete batch is
handled.

The company coordinator normally copies a lifecycle result as a non-lifecycle
`status` message. Set `payload.bridgeEventType` to the original class and include
only sanitized correlation fields such as `sourceRunId`, `sourceMessageId`,
`taskId`, and `dispatchId`. This avoids forging a second `worker_done` from the
wrong terminal while preserving the user-facing event type.

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
