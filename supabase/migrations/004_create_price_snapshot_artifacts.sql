-- Generated public graphs are data, not deployment artifacts.
-- Apply before the web/producer cutover; no changes to existing news_posts.
BEGIN;
CREATE TABLE IF NOT EXISTS public.price_snapshot_artifacts (
  date date PRIMARY KEY,
  html text NOT NULL CHECK (octet_length(html) BETWEEN 1 AND 2097152),
  sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.price_snapshot_artifacts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.price_snapshot_artifacts FROM anon, authenticated;
GRANT SELECT ON public.price_snapshot_artifacts TO anon, authenticated;
GRANT ALL ON public.price_snapshot_artifacts TO service_role;
CREATE POLICY "Public graph read" ON public.price_snapshot_artifacts
  FOR SELECT TO anon, authenticated USING (true);
-- No public write policy. Only the existing producer service-role may insert.
COMMIT;
