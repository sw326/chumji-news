CREATE TABLE IF NOT EXISTS ops_public_snapshots (
  kind         text        PRIMARY KEY CHECK (kind IN ('alerts', 'operations')),
  schema_version text      NOT NULL,
  payload      jsonb       NOT NULL,
  generated_at timestamptz NOT NULL,
  updated_at   timestamptz DEFAULT now()
);

ALTER TABLE ops_public_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public status read" ON ops_public_snapshots
  FOR SELECT USING (true);

COMMENT ON TABLE ops_public_snapshots IS
  'Redacted read-only status snapshots. No tokens, controls, or private runtime paths.';
