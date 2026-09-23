# Durable price snapshot publication

`run_price_snapshot.sh` collects and validates the four configured items, checks
the report/HTML hashes, inserts an immutable dated graph into Supabase, verifies
the public graph byte-for-byte, updates the existing summary, then sends the
existing Telegram notification. **Daily publication no longer deploys the web.**

The web reads `price_snapshot_artifacts` with its existing anon key. Public access
is SELECT-only; insertion uses the producer's existing service-role credential.
The SQL migration does not alter `news_posts` or its policies. Missing graphs are
404; database failures and corrupt artifacts are 503, with no negative caching.

## Compatibility

- `/prices/YYYY-MM-DD` and `/fresh-food/YYYY-MM-DD/index.html` remain unchanged.
- Checked-in historical dated files still serve directly. Other dated URLs fall
  back to the database API, so a clean Git deploy needs no generated local files.
- `/fresh-food/index.html` resolves to the newest stored graph, not the old Git
  template. That template stays in the repository for the local generator.
- An existing date is immutable: same-byte retries succeed; different bytes fail
  closed. Correcting an already-published date requires a reviewed data change.
- `--dry-run` collects and validates locally but never writes externally. Archive
  and Git releases use the same path; no Vercel CLI/project file is required.
- Data, logs and credentials remain outside Git. The wrapper still takes existing
  `FRESH_PRICE_*` SecretRef paths and does not change notification recipients.

## Validation

```sh
npm run check
python3 -m unittest discover -s operations/producers/prices/tests -v
bash -n operations/producers/prices/run_price_snapshot.sh
# Read-only inventory; no credentials needed, no publication:
node scripts/price-artifacts.mjs --archive "$FRESH_PRICE_OUTPUT_ROOT" --static-root public/fresh-food
# Optional full integration, two real Next builds against local REST fixtures:
node operations/producers/prices/tests/check_web_redeploy.mjs "$FRESH_PRICE_OUTPUT_ROOT"
```

The integration fixture is a local HTTP service holding actual archived bytes;
it does not establish that production SQL/RLS or Vercel has been migrated.

## Cutover — approval required, not performed by committing this code

1. Recheck remote main, the live Vercel alias and the price cron's exact command,
   next run and running state. Record the current deployment and command for
   rollback. Do not race the 09:20 publisher; do not replay the job.
2. Apply `supabase/migrations/004_create_price_snapshot_artifacts.sql` to the
   existing database. Verify anon/authenticated SELECT and no write grants; the
   service-role retains insertion. No new credentials or web write key.
3. Re-run the complete inventory, comparing dates with the existing price-summary
   rows. Load the existing producer environment through the protected runtime
   path, then add `--publish` to the inventory command. Each insert is followed
   by full HTML/hash readback. A conflict stops rather than overwriting history;
   retries resume safely. This command never updates summaries or sends Telegram.
4. Confirm anon reads return the same hashes. Only then fast-forward the reviewed
   code to remote `main`, allowing the already-known automatic web deployment.
   Verify deployment READY, production alias identity, `npm run verify:production`
   and all dated graph bytes via `scripts/verify-price-artifact.mjs`. Verify latest
   points to the latest stored date. A 200 login page is not a valid graph.
5. Install an immutable archive of the exact tested commit. Change **only the
   price job's executable path** to that release's
   `operations/producers/prices/run_price_snapshot.sh`. Keep its 09:20 schedule,
   delivery settings, environment and failure alerts. Do not move the shared
   `chumji-news-current` pointer (other producers use it). Do not run the job to
   test notification delivery; verify the next scheduled execution separately.

### Rollback and partial failures

- Before web deployment: leave the old producer/alias unchanged. The additive
  table and inserted public artifacts may remain; do not delete preserved data.
- Failed web verification: promote the recorded old deployment. Do not change
  the producer until the new web is healthy.
- Failed producer switch: retain/restore its recorded prior executable path and
  known-good web deployment. This restores the old behavior, including its known
  historical-file limitation; it is a recovery action, not the permanent fix.
- An artifact save or public-byte verification failure stops before summary and
  notification. A later summary/Telegram failure may leave a stored graph, as
  before; no automatic replay/backfill of notifications is introduced.

## Review evidence (2026-09-23)

- Existing DB price summaries and recoverable artifacts matched 67 dates:
  38 tracked historical files plus 29 local runs, 2026-07-17 through 2026-09-23.
- The pre-change production deployment served today's graph but returned 404
  for yesterday after the normal daily publish: the loss is not JEV-specific.
- Two local production builds each served all 67 original dated byte streams;
  latest, invalid/missing dates, database failure and recovery passed.
- Production SQL migration, data import, web deployment and cron cutover remain
  unperformed at this review milestone. This section is evidence, not live state.

## Production cutover evidence (2026-09-23)

- Approved migration applied to the personal project through its authenticated
  Supabase console. RLS enabled; public roles read-only; service-role INSERT.
- All 67 dated artifacts imported without altering summaries or sending messages.
  Service-role and anon full-byte readback matched the validated inventory.
- Code `87e61b3` reached main; CI succeeded and Vercel deployment
  `dpl_4ChFyNXXkgfYSxbVBB5KmeZF292r` became READY. Production seven-route smoke
  and 67 dated graph hashes plus latest all passed.
- Price cron executable alone moved to the immutable full-SHA release. Schedule,
  recipient, delivery, timeout and failure alert unchanged; shared link untouched.
- First scheduled run on the new path (2026-09-24 09:20 KST) is not yet verified.
  Rollback references live in the operations architecture document.
