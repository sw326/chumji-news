# Trend news: responsibility and stop procedure

Reviewed: 2026-09-30. This is the operating contract for the existing trend
briefing, not a new schedule or a grant of additional authority. Runtime job
configuration and publication receipts remain authoritative for current state.

## Assigned responsibility

| Field | Contract |
| --- | --- |
| Purpose | Produce the existing daily technology trend briefing, including transparent collection completeness. It is not a continuous breaking-news monitor. |
| Inputs | GitHub Trending, GeekNews, Hacker News, Lobsters, Reddit technology and ZDNet Korea; collected source content and supported engagement metrics only. |
| Trigger | Existing `gpt-trend` automation, daily 13:00 Asia/Seoul. Read its live configuration before changing or stopping it. |
| Selection | Keep current freshness, evidence, quota, URL deduplication and seven-KST-date GitHub repeat exclusions; do not fill a target count with unsupported items. |
| Output | Existing web trend briefing and its existing Telegram News link notification. The publication adapter, not scheduler announce delivery, sends the link. |
| Collection degradation | Add one code-generated notice in the web briefing. HN partial metadata loss is distinct from an unavailable source. No extra message is sent. |
| Empty selection | With at least one successfully queried source, produce a deterministic no-selected-articles briefing without a model call; preserve any degradation notice. |
| Failure | All sources unavailable, audit failure, or invalid summary: exit nonzero without normal publication. Existing scheduler failure routing/cooldown applies; read it live rather than inferring immediate delivery from a failed run. |
| Limits | Current job timeout is 1800 seconds. The summarization adapter has a 900-second per-attempt timeout and its existing fallback chain. These are limits, not measured runtime or a newly imposed monetary cap. |
| Duration | Existing recurring responsibility continues until explicitly changed or stopped. No new expiry, polling loop or retry schedule is introduced. |
| Exclusions | No manual replay/backfill, new source, paid service purchase, audience change, account change, or unrelated task monitoring under this responsibility. |

## Readback and completion evidence

1. Identify the existing job through the supported automation list/get tools;
   retain the returned ID rather than deriving one from the display name.
2. Read schedule, enabled state, exact command, timeout, delivery, failure route,
   current run state and last result. Read run history if accessible. A scoped
   `not found` is not proof that the job does not exist; do not inspect raw
   scheduler storage or recreate a job to bypass that result.
3. Distinguish collection health, model completion, database publication and
   Telegram delivery. Scheduler `ok` alone is not evidence that all sources
   were collected. `delivery.mode=none` does not mean the publisher sends nothing.
4. Use the daily audit for source health; use existing publication results and
   receipts for completed delivery. Preserve unknown/partial delivery states.
   Do not replay a publishing job merely to obtain a clearer status.

## Stop requests

The following is a procedure, not an automatic cancellation implementation.
No job was stopped to validate this document.

1. **Resolve the user's scope from the request and conversation.** "Stop this
   run" concerns current work; "stop the daily trend briefing" includes future
   scheduled runs. If it remains ambiguous, stop initiating new work for the
   current request and clarify current-only versus recurring cancellation before
   changing the schedule. Existing explicit authority does not need to be asked
   for again. A request to end this development discussion is not cancellation
   of the daily briefing.
2. **Inventory separately:** current command process/run, the active
   `cron-trend-*` summarization session (and any actually delegated tasks), the
   future recurring automation, and completed publication/delivery. Match the
   exact session/PID tree to this job; never use broad process-name kills or
   stop the Gateway to cancel one news job.
3. **If recurring cancellation is requested:** disable the existing automation
   through the supported update operation and read it back. Prefer reversible
   disablement over deletion. Do not infer that this cancels a running command.
4. **If current work must stop:** use a supported run/session cancellation where
   available. The automation API used in this review exposes schedule management
   but no current-command cancel operation. Check the installed runtime's actual
   capability before promising cancellation. If scoped process termination is
   needed, first identify the exact process tree and stage, preserve recovery
   evidence, and operate only within the user's stop authority. Killing the CLI
   client is not proof that its Gateway-side model session stopped. Recheck both
   local execution and remote/session state; report anything still running or
   unverified. Do not broaden this into a service restart.
5. **If publication already began:** cancellation cannot retract completed
   writes or messages. Check whether the database write and Telegram delivery
   each completed. Preserve receipts; an interrupted request without a receipt
   may still have delivered. Do not automatically retry, remove a published
   article, or retract a message. Those are separate requested actions.
6. **Report the result by scope:** current run stopped/running/unverified;
   summarization/delegated tasks stopped/running/unverified; future schedule
   disabled/unchanged; completed publications left intact. "Stopped" is only
   used for a scope whose state was actually read back.

For a one-run skip, do not silently disable the recurring job indefinitely or
create a new re-enable automation. Establish the supported skip mechanism and
the intended next scheduled run first.

## Collection-health release and rollback

The implementation is `cbe6bd6` on `fix/trend-collection-health`. It was
cherry-picked onto the actual pre-cutover runtime, producing release
`1ca8cc4aa5bcb6e348d04d773da71c593f5adef4` on
`release/trend-collection-health`. Only the six news files differ from the
previous runtime; unrelated changes on the development branch were not deployed.

On 2026-09-30, the OpenClaw news current link was atomically changed from
`9c4ee6c12a83a4c5155280e093d39a62a7b937f2` to that release. Evidence:

- 55 offline news tests passed on the exact release commit.
- All 190 staged tracked files matched Git object bytes; executable entrypoints
  retained their executable mode. The old release was retained unchanged.
- Public collector-only smoke check: six sources `ok`, 24 selected articles,
  zero collection errors. No model, database publication or Telegram send.
- No news pipeline was active at cutover. News job configuration revisions,
  last runs and next runs were identical before/after. The independent price
  job configuration was unchanged as well.
- The next scheduled trend run was 2026-09-30 13:00 KST. Its actual publication
  is **not yet verified by this deployment record**. No manual replay was run.
- Run history lookup returned `not found`; supported job get/last diagnostics,
  process inspection and release verification were used without bypassing that
  history limitation.

Rollback only when requested or required by the approved cutover recovery:
verify the current link and that no news job is active, then atomically repoint
`~/.openclaw/services/chumji-news-current` to retained release
`~/.openclaw/services/chumji-news-releases/9c4ee6c12a83a4c5155280e093d39a62a7b937f2`.
Read back the link and unchanged scheduler configuration. Do not rerun a
publishing job or alter external receipts. If another deployment advanced the
link, reassess instead of blindly restoring this dated target.

The older GitHub-only rollback reference in the producer README belongs to its
historical rollout, not this collection-health deployment.

## Design references

- [Production news collector contract](../../producers/news/README.md)
- [Current architecture](current-architecture.md)
- [Dots tasks and memory](https://learn.chatgpt.com/docs/dots/tasks-and-memory):
  explicitly scoped responsibilities and separate schedule cancellation.
- [Dots controls](https://learn.chatgpt.com/docs/dots/controls): stopping main
  work, delegated work and future schedules has different effects. This runbook
  adapts that distinction; it does not imply identical OpenClaw capabilities.
