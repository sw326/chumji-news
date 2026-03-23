-- 참치뉴스 news_posts 테이블
-- Supabase Dashboard > SQL Editor 에서 실행하세요.

CREATE TABLE IF NOT EXISTS news_posts (
  id         uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  date       date        NOT NULL,
  category   text        NOT NULL CHECK (category IN ('news', 'it', 'trend', 'realestate')),
  content    text        NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_news_posts_date_cat
  ON news_posts (date DESC, category);

-- RLS: 모든 사용자가 읽기 가능, 쓰기는 service_role만
ALTER TABLE news_posts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON news_posts
  FOR SELECT USING (true);

CREATE POLICY "Allow service_role insert" ON news_posts
  FOR INSERT WITH CHECK (true);
