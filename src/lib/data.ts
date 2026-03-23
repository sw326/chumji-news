import { supabase } from "./supabase";
import { NewsPost, Category } from "./types";

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
