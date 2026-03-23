import { supabase } from "./supabase";
import { mockPosts } from "./mock-data";
import { NewsPost, Category } from "./types";

export async function getAllPosts(): Promise<NewsPost[]> {
  if (supabase) {
    const { data, error } = await supabase
      .from("news_posts")
      .select("*")
      .order("date", { ascending: false })
      .order("created_at", { ascending: false });

    if (!error && data) return data as NewsPost[];
  }

  return mockPosts;
}

export async function getPostsByCategory(
  category: Category
): Promise<NewsPost[]> {
  if (supabase) {
    const { data, error } = await supabase
      .from("news_posts")
      .select("*")
      .eq("category", category)
      .order("date", { ascending: false })
      .order("created_at", { ascending: false });

    if (!error && data) return data as NewsPost[];
  }

  return mockPosts.filter((p) => p.category === category);
}

export async function getPost(
  date: string,
  category: Category
): Promise<NewsPost | null> {
  if (supabase) {
    const { data, error } = await supabase
      .from("news_posts")
      .select("*")
      .eq("date", date)
      .eq("category", category)
      .order("created_at", { ascending: false })
      .limit(1)
      .single();

    if (!error && data) return data as NewsPost;
  }

  return mockPosts.find((p) => p.date === date && p.category === category) ?? null;
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
