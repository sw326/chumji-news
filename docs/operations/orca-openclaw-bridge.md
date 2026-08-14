# Orca → OpenClaw bridge design

Status: prototype validated on 2026-08-14; permanent installation not approved.

## Objective

Keep task orchestration and workers local to the company computer while using
the personal Mac OpenClaw agent as the Telegram control plane, approval surface,
and sanitized personal work-history layer.

## Data flow

```text
company coordinator
  -> sanitized copy to dedicated observer Run
  -> blocking Orca check --wait over Mac-initiated SSH
  -> local bridge validation/redaction/journal
  -> OpenClaw agent session
  -> optional Telegram delivery after cutover approval
```

The observer Run is a separate consumer. Reading the production coordinator
mailbox would race its coordinator and is prohibited.

## Prototype evidence

The read-only/runtime-scoped probe established:

1. A dedicated observer terminal and Run can be created without changing the
   active project checkout or service.
2. The active company coordinator can send a sanitized `status` copy to that
   observer Run.
3. A Mac-initiated SSH command using `orca orchestration check --wait` receives
   the event immediately without periodic polling.
4. An isolated OpenClaw test session records and processes the event.
5. Orca delivery is acknowledged only after the OpenClaw call succeeds.

Direct Orca federation remains the preferred future transport, but the saved
Mac environment references a prior company runtime identity and did not produce
a live response during this probe. The SSH long-wait transport is therefore the
validated fallback and does not require exposing the loopback OpenClaw Gateway.

## Delivery semantics

- Transport is at-least-once until ACK.
- Event IDs are journaled locally.
- A known delivered replay skips the OpenClaw call and retries ACK.
- A crash or unknown result during OpenClaw invocation is fail-closed: the event
  is left unacknowledged and automatic replay is refused for manual
  reconciliation.
- One Orca Delivery may contain messages outside the wake-up filter. Every row
  is classified before the Delivery is acknowledged.

Lifecycle messages are not forged or replayed from the coordinator terminal.
The coordinator emits a normal `status` copy with
`payload.bridgeEventType=<worker_done|escalation|question|decision_gate>` and
sanitized source correlation IDs. The bridge exposes that copied class as the
effective event type while retaining `transport_type=status` in the envelope.

User answers follow the reverse control-mail path. The bridge stores the copied
`sourceRunId` and source correlation IDs, sends the answer as a high-priority
`status` message to that Run, and leaves the authoritative `reply` or
`gate-resolve` action to its coordinator. User text is transferred over SSH
stdin to a fixed remote Python launcher, so it is not interpolated into a
remote shell command.

## Information boundary

Allowed event classes:

- completion and failure summaries;
- escalation and decision requests;
- task/dispatch correlation IDs;
- commit, validation, and artifact references suitable for a work-history
  summary.

Excluded data:

- heartbeat noise and raw terminal output;
- credentials, tokens, cookies, private keys, and environment dumps;
- company source code or unrestricted internal file content;
- arbitrary commands embedded in message bodies.

The company coordinator must emit a sanitized summary. The bridge additionally
redacts common credential assignments, bounds text sizes, and projects only
allowlisted structured payload fields.

## Remaining cutover gates

Before permanent service installation:

1. Decide the long-term service owner and release path.
2. Create a permanent observer Run and document recovery after Orca restart.
3. Validate a real `worker_done`, `question`, and `decision_gate` copy.
4. Verify the Telegram-to-coordinator response path with a real company
   coordinator and confirm that it performs the authoritative reply/gate action.
5. Validate network loss, Mac reboot, company reboot, duplicate Delivery, and
   ambiguous OpenClaw-result recovery.
6. Review the disabled LaunchAgent template, install only a reviewed release,
   and update `current-architecture.md` after observed live verification.
7. Remove the legacy polling loop only after bridge health is proven.
