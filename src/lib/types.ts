export type Category =
  | "news"
  | "it"
  | "trend"
  | "realestate"
  | "moltbook"
  | "opendata"
  | "system"
  | "issues"
  | "reddit";

export interface NewsPost {
  id: string;
  date: string; // YYYY-MM-DD
  category: Category;
  content: string;
  created_at: string;
}

export interface NewsScrap {
  id: string;
  user_id: string;
  article_key: string;
  post_id: string;
  post_date: string;
  category: Category;
  emoji: string;
  title: string;
  description: string;
  source_text: string;
  source_url: string;
  created_at: string;
}

export type NewsScrapDraft = Omit<NewsScrap, "id" | "user_id" | "created_at">;

export const CATEGORY_LABELS: Record<Category, string> = {
  news: "뉴스",
  it: "IT",
  trend: "트렌드",
  realestate: "강남3구",
  moltbook: "몰트북",
  opendata: "공공데이터",
  system: "시스템",
  issues: "이슈",
  reddit: "Reddit",
};

export const CATEGORIES: Category[] = [
  "news",
  "it",
  "trend",
  "realestate",
  "moltbook",
  "opendata",
  "system",
  "issues",
  "reddit",
];
