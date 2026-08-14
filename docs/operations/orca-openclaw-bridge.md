# Orca → OpenClaw bridge design

Status: production cutover validated on 2026-08-14.

Observed deployment:

- release commit: `7ab83e9` (initial production commit `43231c4`,
  source-equivalent prototype commit `19321ad`);
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
registered authoritative source Run
  -> dynamic coordinator-handle resolution
  -> non-consuming Orca check --peek --wait
  -> lifecycle summary projection
  -> local bridge validation/redaction/journal
  -> OpenClaw agent session
  -> optional Telegram delivery

company coordinator
  -> optional sanitized milestone status to dedicated observer Run
  -> blocking Orca check --wait with ACK over Mac-initiated SSH
  -> local bridge validation/redaction/journal
  -> OpenClaw agent session
  -> optional Telegram delivery
```

The source watcher never consumes or acknowledges production Run mail. It uses
`--peek --wait`, stores source message IDs for deduplication, and lets the
authoritative coordinator retain the only ACK and lifecycle authority. When no
source event exists the SSH call blocks; if an already-forwarded event remains
unread, the watcher backs off for 60 seconds before checking for additions.

The observer Run remains a separate consumer for curated status summaries. It
must not be used as the required producer for lifecycle events because terminal
rebinding or an idle coordinator can otherwise suppress feedback.

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
The source watcher exposes the original lifecycle class as untrusted status
data, drops unrestricted payload fields, and does not ACK the source Delivery.
The coordinator may still emit normal `status` copies for higher-level,
sanitized milestones that are not represented by lifecycle events.

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

Automatic source lifecycle bodies are redacted, bounded, and projected to
allowlisted structured payload fields. A coordinator-authored observer
`status` must already be a sanitized summary before the bridge applies the same
defense-in-depth filters.

## Verified cutover gates

1. Sanitized company status reached the owner Telegram DM exactly once.
2. OpenClaw success preceded Orca Delivery ACK.
3. A copied question retained source correlation and a test owner response
   returned to the source Run without coordinator impersonation.
4. Forced SSH-child termination recovered automatically within the renewable
   waiter deadline.
5. Forced LaunchAgent process termination produced a new process and restored
   the long-wait connection without restarting the OpenClaw Gateway.
6. A real owner Telegram response to bridge event `msg_b32226615737` returned
   to isolated source Run `run_8ba58b52e673` as `msg_7d5b3c7ba422`, preserving
   source message and question correlation and clearing the pending response.
7. macOS `/tmp` resolves to `/private/tmp`; release `fb951ba` validates against
   the resolved approved directory so response files remain constrained to the
   intended temporary directory on macOS.
8. Release `8149215` serializes cross-process state updates with an advisory
   lock and reload-before-mutate transaction. A stale long-running bridge can
   no longer overwrite a response status written by the response CLI; the
   regression suite passes 16/16 and the verified E2E event has no pending
   correlation.
9. Release `7ab83e9` dynamically resolved the authoritative coordinator handle
   for source Run `run_6b236f7b699a`, detected previously missed
   `worker_done msg_5a15b79096ea`, and delivered it without source ACK. This
   closed the terminal-binding failure that had suppressed feedback after
   16:53 KST.

## Remaining operational checks

1. Validate real project `question` and `decision_gate` events through the
   automatic source watcher.
2. Confirm a project coordinator consumes returned owner control mail and
   performs the authoritative reply/gate action.
3. Validate full Mac and company reboots at a maintenance window; do not reboot
   while project workers or production operations are active.
4. Refresh direct Orca federation identity and compare it with the validated
   SSH fallback before any transport cutover.

## Registering another source Run

1. Use the durable Orca Run ID, never a terminal handle.
2. Add one unique object to private config `watched_runs` with `run_id`, a
   60-second wait timeout, and a 60-second duplicate-backoff interval.
3. Run the bridge unit suite and Python compile check from the development
   checkout.
4. Install a commit-addressed immutable release and restart the LaunchAgent
   only under an approved operations change.
5. Verify a source lifecycle event appears once in the bridge journal while the
   source Run Delivery remains unacknowledged until its coordinator handles it.

Other OpenClaw sessions discover this procedure through the common workspace
`AGENTS.md`; mutable Run registrations remain only in the private bridge config.
