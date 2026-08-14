# Orca → OpenClaw bridge design

Status: production cutover validated on 2026-08-14.

Observed deployment:

- release commit: `43231c4` (source-equivalent prototype commit `19321ad`);
- LaunchAgent: `com.chumji.orca-openclaw-bridge`;
- company observer Run: `run_1a897b1b8eb5`;
- observer terminal: `term_81ce6937-4132-4dab-88ae-a1e7f4523fa4`;
- transport: renewable 60-second SSH `check --wait`;
- OpenClaw session: dedicated `agent:main:orca-bridge`, delivered to the owner
  Telegram DM.

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

The initial permanent observer `run_921920e99f30` used a 900-second wait. A
forced client restart proved that Orca retains a disconnected actionable waiter
until its deadline, delaying replacement. It was superseded before normal use
by the 60-second renewable observer above. The earlier Run is retained only as
cutover evidence and must not receive new copies.

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

## Verified cutover gates

1. Sanitized company status reached the owner Telegram DM exactly once.
2. OpenClaw success preceded Orca Delivery ACK.
3. A copied question retained source correlation and a test owner response
   returned to the source Run without coordinator impersonation.
4. Forced SSH-child termination recovered automatically within the renewable
   waiter deadline.
5. Forced LaunchAgent process termination produced a new process and restored
   the long-wait connection without restarting the OpenClaw Gateway.

## Remaining operational checks

1. Validate a real project `worker_done`, `question`, and `decision_gate` copy.
2. Confirm a project coordinator consumes returned owner control mail and
   performs the authoritative reply/gate action.
3. Validate full Mac and company reboots at a maintenance window; do not reboot
   while project workers or production operations are active.
4. Refresh direct Orca federation identity and compare it with the validated
   SSH fallback before any transport cutover.
