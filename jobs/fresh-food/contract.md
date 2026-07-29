# Fresh Food Batch Contract

Status: shadow implementation, inactive.

## Ownership

- Target owner: `ops`.
- Current live owner and publication path remain unchanged until cutover approval.
- Vercel production, Supabase production, live schedulers, and legacy output paths
  remain out of scope.

## Inputs

- Product/source list from the #11 inventory.
- Approved legacy snapshot samples.
- Preview-only output destination.
- Optional provider/API credentials referenced only by SecretRef.

## Outputs

- Shadow price snapshot.
- Normalized product price records.
- Preview-only web artifact bundle.
- Job-run summary.
- Last-success marker.
- Diff report against approved legacy snapshots.
- Date-partitioned `shadow-status.json` with model and publication routes.

## Inactive Schedule Metadata

- Name: `fresh-food.snapshot.shadow`.
- Cadence: `inventory-confirmed`.
- Mode: `shadow-disabled-by-default`.

## Model, API, And SecretRefs

| Name | Type | Purpose |
| --- | --- | --- |
| `fresh-food.normalizer.model.default` | model policy | Optional normalization route; record `none` if unused. |
| `fresh-food.sources.http` | API | Public source fetching. |
| `fresh-food.preview.build` | API | Preview artifact build boundary. |
| `fresh-food.source.api` | SecretRef | Source API credential lookup if needed. |
| `fresh-food.vercel.preview` | SecretRef | Preview-only deployment credential lookup. |
| `fresh-food.supabase.preview` | SecretRef | Preview-only data credential lookup. |

## GUI/Login Dependency

Shadow implementation must not require personal browser login, CAPTCHA solving,
keychain user session, purchasing account cookies, or private GUI state.

## Shadow Validation

- Production publication disabled.
- Separate shadow output root.
- Compare product coverage, price values, timestamps, missing items, and schema
  against legacy samples.
- Verify preview artifact target is not production Vercel or Supabase.
- Record `model_route=none` and `publication=disabled` in every shadow status.

## Duplicate Prevention

- Snapshot key: `fresh-food:{market}:{observedDate}:{sourceId}`.
- Product key: normalized product ID or canonical source URL.
- Shadow outputs must not overwrite legacy snapshots or web assets.

## Cutover And Rollback

Cutover requires separate approval with scheduler, Vercel/Supabase targets,
revision, validation evidence, SecretRef readiness, rollback plan, and legacy
disable target. Rollback before cutover is deleting shadow artifacts only.

## Completion Evidence

- Passing contract validation.
- Shadow snapshot report.
- Preview artifact path.
- Legacy parity diff.
- Secret scan with no credential values.
