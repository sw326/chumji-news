import { supabase } from "./supabase";
import { NewsPost, Category } from "./types";

export const PAGE_SIZE = 20;
export const PRICE_SNAPSHOT_CATEGORY: Category = "opendata";
export const PRICE_SNAPSHOT_PREFIX = "# 신선식품 가격 스냅샷";

export async function getAllPosts(): Promise<NewsPost[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .order("date", { ascending: false })
    .order("created_at", { ascending: false });

  if (error || !data) return [];
  return data as NewsPost[];
}

export async function getPostsByCategory(
  category: Category
): Promise<NewsPost[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("category", category)
    .order("date", { ascending: false })
    .order("created_at", { ascending: false });

  if (error || !data) return [];
  return data as NewsPost[];
}

export async function getPost(
  date: string,
  category: Category
): Promise<NewsPost | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("date", date)
    .eq("category", category)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) return null;
  return data as NewsPost;
}

export async function getLatestPostByCategory(
  category: Category
): Promise<NewsPost | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("category", category)
    .order("date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) return null;
  return data as NewsPost;
}

export async function getRecentPostsByCategory(
  category: Category,
  limit = 14
): Promise<NewsPost[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("category", category)
    .order("date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error || !data) return [];
  return data as NewsPost[];
}

export async function getLatestPriceSnapshot(): Promise<NewsPost | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("category", PRICE_SNAPSHOT_CATEGORY)
    .ilike("content", `${PRICE_SNAPSHOT_PREFIX}%`)
    .order("date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) return null;
  return data as NewsPost;
}

export async function getRecentPriceSnapshots(limit = 14): Promise<NewsPost[]> {
  if (!supabase) return [];
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("category", PRICE_SNAPSHOT_CATEGORY)
    .ilike("content", `${PRICE_SNAPSHOT_PREFIX}%`)
    .order("date", { ascending: false })
    .order("created_at", { ascending: false })
    .limit(limit);

  if (error || !data) return [];
  return data as NewsPost[];
}

export async function getPriceSnapshot(date: string): Promise<NewsPost | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("news_posts")
    .select("*")
    .eq("date", date)
    .eq("category", PRICE_SNAPSHOT_CATEGORY)
    .ilike("content", `${PRICE_SNAPSHOT_PREFIX}%`)
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error || !data) return null;
  return data as NewsPost;
}

/** 페이지네이션 조회 (0-based page) */
export async function fetchPostsPage(
  page: number,
  category?: Category | "all"
): Promise<{ posts: NewsPost[]; hasMore: boolean }> {
  if (!supabase) return { posts: [], hasMore: false };

  const from = page * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("news_posts")
    .select("*")
    .order("date", { ascending: false })
    .order("created_at", { ascending: false })
    .range(from, to);

  if (category && category !== "all") {
    query = query.eq("category", category);
  }

  const { data, error } = await query;
  if (error || !data) return { posts: [], hasMore: false };

  return {
    posts: data as NewsPost[],
    hasMore: data.length === PAGE_SIZE,
  };
}

/** Group posts by date, sorted descending */
export function groupByDate(posts: NewsPost[]): Map<string, NewsPost[]> {
  const map = new Map<string, NewsPost[]>();
  for (const post of posts) {
    const existing = map.get(post.date) ?? [];
    existing.push(post);
    map.set(post.date, existing);
  }
  return map;
}
