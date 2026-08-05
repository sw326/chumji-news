-- Per-user article scraps. Authentication is handled by Supabase Auth.
CREATE TABLE IF NOT EXISTS news_scraps (
  id           uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id      uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  article_key  text        NOT NULL,
  post_id      uuid        NOT NULL REFERENCES news_posts(id) ON DELETE CASCADE,
  post_date    date        NOT NULL,
  category     text        NOT NULL,
  emoji        text        NOT NULL DEFAULT '',
  title        text        NOT NULL,
  description  text        NOT NULL DEFAULT '',
  source_text  text        NOT NULL DEFAULT '',
  source_url   text        NOT NULL DEFAULT '',
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, article_key)
);

CREATE INDEX IF NOT EXISTS idx_news_scraps_user_created
  ON news_scraps (user_id, created_at DESC);

ALTER TABLE news_scraps ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own scraps" ON news_scraps
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can insert own scraps" ON news_scraps
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);

CREATE POLICY "Users can delete own scraps" ON news_scraps
  FOR DELETE TO authenticated USING ((SELECT auth.uid()) = user_id);

