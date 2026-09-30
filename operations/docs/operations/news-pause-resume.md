# News run pause and resume

This is an **opt-in local controller**, not a new schedule or Gateway service.
The existing `run_profile.sh PROFILE --publish` cron command remains unmanaged
and unchanged in invocation. Deploying or switching it to this controller needs
an explicit cutover. No existing scheduled run was stopped or replayed to test it.

## Interface

From the reviewed repository/release root, use a new private directory outside Git:

```bash
python3 operations/producers/news/task_control.py start trend \
  --directory "$HOME/.local/state/chumji-news/runs/example" --start-paused
python3 operations/producers/news/task_control.py status \
  "$HOME/.local/state/chumji-news/runs/example"
python3 operations/producers/news/task_control.py resume \
  "$HOME/.local/state/chumji-news/runs/example"
```

`start` without `--start-paused` runs immediately. `morning`, `it`, and `trend`
are supported. Default mode is dry-run: **it still collects and calls the model**,
but never calls the publisher. Only an explicitly authorized `start --publish`
creates a publishing run. Resume preserves its original mode/profile; it cannot
promote a dry-run into a publishing run. `--directory` must not already exist.

To request a cooperative pause from another turn/process:

```bash
python3 operations/producers/news/task_control.py pause \
  "$HOME/.local/state/chumji-news/runs/example"
```

The running stage finishes before the next stage begins. A pause command's
success means **request recorded**, not stopped. Inspect `status`:

- `paused` with `local_worker_active: false`: the local pipeline reached a safe
  checkpoint. The execution command returns exit code **75**, not success.
- `running` with `pause_requested: true`: it is still finishing collection,
  summarization, or publication. Do not report it stopped.
- `completed`: work finished; resume is rejected to prevent replay.
- `needs_attention`: a model or publication stage exited without a recorded
  completion. Automatic resume is blocked; inspect the original session and
  existing publication receipts before any separately authorized recovery.
- `interrupted_unverified`: the controller disappeared without a terminal
  checkpoint and no local worker lock remains. This is not remote cancellation.

`schedule: unchanged` and `remote_session: not_inspected` are explicit limits.
This controller never disables cron, cancels a Gateway model session, retracts a
publication, kills process-name matches, or starts a replacement session. If
immediate remote cancellation is required, use the supported caller-scoped
controls and the [responsibility runbook](trend-news-responsibility.md).

## Checkpoint and recovery contract

- Collect and summarize completion retain `source.json` and validated final
  `briefing.md`; completed stages are skipped on resume.
- A worker lock is inherited by the pipeline. Killing only the controller does
  not release ownership while its local child is alive; duplicate resume fails.
- A separate state lock serializes pause requests with the next-stage intent.
  If publication intent wins the race, the publisher may finish despite a later
  pause. The controller does not promise rollback or exactly-once network writes.
- Code and prompt assets, relevant environment, and completed artifacts are
  fingerprinted and rechecked. Publishing runs also fingerprint credential/config
  file contents without persisting their values. Changes block continuation.
- A publishing run from a different KST date is blocked at resume and before
  publication. Dry-run output retains the original date for inspection.
- A failed read-only collection may be resumed. An uncertain model/publication
  attempt may not. Do not edit `state.json` to bypass this guard; a receipt check
  and explicit recovery decision are separate from this controller.

The directory and new files are private (0700/0600 via umask). Public source,
prompt and summary artifacts intentionally remain for recovery; they are not
automatically copied to memory/wiki. Publication credentials are written only to
an ephemeral temporary directory, removed on normal exit. A hard process kill
can prevent any shell cleanup, so do not describe this as guaranteed erasure.
The hashes detect accidental changes, not hostile modification by the same user;
this is not a sandbox or authorization boundary. Retention/cleanup is explicit,
and no new cleanup timer is installed.

## Verification and rollout boundary

```bash
python3 -m unittest discover -s operations/producers/news/tests -q
bash -n operations/producers/news/run_profile.sh
git diff --check
```

The controller tests run the real Python controller and Bash entrypoint with
fake collection, model and publication adapters in private temporary trees.
They cover stage reuse, cooperative pause, concurrent resume, inherited locks
after controller death, changed code/prompts/artifacts/config, stale publication,
unknown model/publication outcomes, and existing morning/IT/trend behavior.
No production credentials, network requests, publication, or scheduler mutation
are used. The existing publisher's deduplication tests remain in the same suite.
