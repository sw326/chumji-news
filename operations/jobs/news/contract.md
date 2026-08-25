# News Batch Contract

Status: shadow implementation, inactive.

## Ownership

- Target owner: `ops`.
- Current live owner remains unchanged until cutover approval.
- OpenClaw, personal Telegram conversations, Claude personal session billing/auth,
  Gemini personal auth, GUI state, and live schedulers remain out of scope.

## Inputs

- Public news, IT, and trend source lists from the #11 inventory. A public
  Reddit feed may be one trend discovery source, but there is no standalone
  Reddit product profile.
- Approved legacy output samples for parity comparison.
- Optional model/API credentials referenced only by SecretRef.
- Existing public-feed collector JSON (`articles` array) for the AI-less route.

## Outputs

- Shadow briefing artifact.
- Source coverage manifest.
- Job-run summary.
- Last-success marker.
- Diff report against approved legacy output samples.
- Deterministic Markdown and run report from the AI-less route.

## Inactive Schedule Metadata

- Name: `news.briefing.shadow`.
- Cadence: `inventory-confirmed`.
- Mode: `shadow-disabled-by-default`.

## Model, API, And SecretRefs

| Name | Type | Purpose |
| --- | --- | --- |
| `news.briefing.model.default` | model policy | Summarization and briefing generation route. |
| `news.sources.http` | API | Public source fetching. |
| `news.model.api` | SecretRef | Ops-owned model API credential lookup. |
| `news.telegram.destination` | SecretRef | Cutover-only Telegram destination lookup. |

## GUI/Login Dependency

Shadow implementation must not require GUI login, keychain user session, personal
Claude session, personal Gemini auth, or OpenClaw runtime state.

The default shadow route is `model_route=none`; `news.model.api` is reserved for
a separately approved, exceptional interpretation route and is not required for
daily collection.

## Shadow Validation

- Publication disabled.
- Separate shadow output root.
- Compare item count, source coverage, output schema, citation presence, and
  briefing language against legacy samples.
- Record run ID, input window, API/model route names, counts, and redacted
  errors.

## Duplicate Prevention

- Run lock key: `news:{inputWindowStart}:{inputWindowEnd}`.
- Item key: canonical URL or upstream ID.
- Telegram/output publication remains disabled until cutover.

## Cutover And Rollback

Cutover requires separate approval with scheduler, revision, validation evidence,
SecretRef readiness, rollback plan, and legacy disable target. Rollback before
cutover is deleting shadow artifacts only.

## Completion Evidence

- Passing contract validation.
- Shadow dry-run report.
- Legacy parity diff.
- Secret scan with no credential values.
