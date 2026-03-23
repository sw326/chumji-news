export type Category = "news" | "it" | "trend" | "realestate" | "moltbook" | "opendata" | "system";

export interface NewsPost {
  id: string;
  date: string; // YYYY-MM-DD
  category: Category;
  content: string;
  created_at: string;
}

export const CATEGORY_LABELS: Record<Category, string> = {
  news: "📰 뉴스",
  it: "💻 IT",
  trend: "🔥 트렌드",
  realestate: "🏠 강남3구",
  moltbook: "🦞 몰트북",
  opendata: "📊 공공데이터",
  system: "⚙️ 시스템",
};

export const CATEGORIES: Category[] = ["news", "it", "trend", "realestate", "moltbook", "opendata", "system"];
