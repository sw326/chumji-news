# Global Intel Batch Contract

Status: shadow implementation, inactive.

## Ownership

- Target owner: `ops`.
- Current live owner remains unchanged until cutover approval.
- OpenClaw, personal Telegram conversations, Claude personal session billing/auth,
  Gemini personal auth, GUI state, and live schedulers remain out of scope.

## Inputs

- Public world-affairs and risk-monitoring source lists from the #11 inventory.
- Approved legacy output samples for parity comparison.
- Optional model/API credentials referenced only by SecretRef.

## Outputs

- Shadow global-intel briefing artifact.
- Source citation manifest.
- Job-run summary.
- Last-success marker.
- Diff report against approved legacy output samples.
- Deterministic source-health and observation briefing.
- ReliefWeb situation-report citations from its public RSS feed.

## Inactive Schedule Metadata

- Name: `global-intel.briefing.shadow`.
- Cadence: `inventory-confirmed`.
- Mode: `shadow-disabled-by-default`.

## Model, API, And SecretRefs

| Name | Type | Purpose |
| --- | --- | --- |
| `global-intel.briefing.model.default` | model policy | Summarization and analysis route. |
| `global-intel.sources.http` | API | Public source fetching. |
| `global-intel.model.api` | SecretRef | Ops-owned model API credential lookup. |
| `global-intel.telegram.destination` | SecretRef | Cutover-only Telegram destination lookup. |

## GUI/Login Dependency

Shadow implementation must not require GUI login, keychain user session, personal
Claude session, personal Gemini auth, or OpenClaw runtime state.

## Shadow Validation

- Publication disabled.
- Separate shadow output root.
- Compare topic coverage, citation count, output structure, risk categories, and
  language against legacy samples.
- Record run ID, input window, API/model route names, counts, and redacted
  errors.
- Record `model_route=none` and `publication=disabled`; aircraft counts must
  not be represented as proof of military activity.

## Duplicate Prevention

- Run lock key: `global-intel:{inputWindowStart}:{inputWindowEnd}`.
- Source key: canonical URL or source-specific event ID.
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
