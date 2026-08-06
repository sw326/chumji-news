ALTER TABLE ops_public_snapshots
  DROP CONSTRAINT IF EXISTS ops_public_snapshots_kind_check;

ALTER TABLE ops_public_snapshots
  ADD CONSTRAINT ops_public_snapshots_kind_check
  CHECK (kind IN ('alerts', 'operations', 'trade-market'));

COMMENT ON TABLE ops_public_snapshots IS
  'Public, read-only alert, operations, and validated trade-market snapshots. No secrets or control endpoints.';
