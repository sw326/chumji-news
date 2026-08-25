# Operations

This directory contains the jobs, services, deployment definitions, security
contracts, and runbooks imported from `sw326/chumji-ops`.

The import reconciles both former ops lines of development and preserves their
Git ancestry. It deliberately excludes `apps/web`: that unfinished fork
duplicated the root `chumji-news` application and is no longer a development
surface. The old market, alerts, and operations UI remains recoverable from Git
history if a specific implementation is later judged worth porting. Any such
work must target the root application and be reviewed as a new feature.

## Transition boundary

Merging this directory changes source ownership only. Existing runtime paths,
schedulers, services, credentials, and deployments remain unchanged until a
separately reviewed cutover updates and verifies them. During the transition,
the old `chumji-ops` checkout may still be the installed runtime source even
though new development belongs here.

Start with `docs/operations/current-architecture.md` before changing any live
component.
