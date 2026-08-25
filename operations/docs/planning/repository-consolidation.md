# Repository consolidation

## Decision

`chumji-news` is the surviving development repository. The production web app
stays at its root, and operational source from `chumji-ops` moves under
`operations/`. Future product and operations development occurs here.

The duplicated `chumji-ops/apps/web` tree is retired rather than merged. It was
created as a preservation import on 2026-07-29, never replaced the original
production development root, and later diverged into an unfinished preview.
Its history remains available through the consolidation merge.

## Included source

- deterministic and shadow jobs;
- alert hub, Orca bridge, and secret-handoff services;
- deployment definitions, manifests, SecretRef rules, and runbooks;
- both formerly divergent `chumji-ops` branch histories.

## Explicitly excluded

- `chumji-ops/apps/web` and its incomplete market, alerts, and operations UI;
- secrets, runtime data, logs, build output, and local configuration;
- any automatic scheduler, service, Vercel, Supabase, or traffic mutation.

## Cutover checklist

1. Validate the root web application and every imported component.
2. Merge the consolidation branch without changing the production web root.
3. Update installed runtime checkouts and command paths one component at a
   time, with read-only state verification and rollback references.
4. Confirm cron and launchd jobs no longer read the old repository checkout.
5. Confirm Vercel production still builds the root `chumji-news` application.
6. Retain the old repository through a rollback window, then archive it rather
   than delete its history.

Repository archive is the final step, not evidence that runtime migration has
already completed.
