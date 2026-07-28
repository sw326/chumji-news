-- issues 카테고리 추가
ALTER TABLE news_posts 
  DROP CONSTRAINT IF EXISTS news_posts_category_check;

ALTER TABLE news_posts 
  ADD CONSTRAINT news_posts_category_check 
  CHECK (category IN ('news', 'it', 'trend', 'realestate', 'moltbook', 'opendata', 'system', 'issues'));
