"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import type { NewsScrap, NewsScrapDraft } from "@/lib/types";

const SCRAPS_PAGE_SIZE = 30;

interface ScrapsCursor {
  createdAt: string;
  id: string;
}

async function fetchScrapsPage(userId: string, cursor: ScrapsCursor | null) {
  if (!supabase) return { scraps: [] as NewsScrap[], hasMore: false, error: "Supabase가 설정되지 않았습니다." };

  let query = supabase
    .from("news_scraps")
    .select("*")
    .eq("user_id", userId)
    .order("created_at", { ascending: false })
    .order("id", { ascending: false })
    .limit(SCRAPS_PAGE_SIZE + 1);

  if (cursor) {
    query = query.or(
      `created_at.lt.${cursor.createdAt},and(created_at.eq.${cursor.createdAt},id.lt.${cursor.id})`
    );
  }

  const { data, error } = await query;
  if (error || !data) {
    return { scraps: [] as NewsScrap[], hasMore: Boolean(cursor), error: error?.message ?? "스크랩을 불러오지 못했습니다." };
  }

  return {
    scraps: data.slice(0, SCRAPS_PAGE_SIZE) as NewsScrap[],
    hasMore: data.length > SCRAPS_PAGE_SIZE,
    error: null,
  };
}

interface ScrapContextValue {
  user: User | null;
  scraps: NewsScrap[];
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  loadError: string;
  loadMoreScraps: () => Promise<void>;
  isScrapped: (articleKey: string) => boolean;
  toggleScrap: (draft: NewsScrapDraft) => Promise<"saved" | "removed" | "login">;
  signIn: (email: string) => Promise<string | null>;
  verifyOtp: (email: string, token: string) => Promise<string | null>;
  signOut: () => Promise<void>;
}

const ScrapContext = createContext<ScrapContextValue | null>(null);

export default function ScrapProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [scraps, setScraps] = useState<NewsScrap[]>([]);
  const [loading, setLoading] = useState(Boolean(supabase));
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [scrapIndex, setScrapIndex] = useState<Map<string, string>>(new Map());
  const loadInFlight = useRef(false);

  const loadScraps = useCallback(async (userId: string) => {
    const [result, indexResult] = await Promise.all([
      fetchScrapsPage(userId, null),
      supabase
        ? supabase.from("news_scraps").select("id, article_key").eq("user_id", userId)
        : Promise.resolve({ data: null, error: new Error("Supabase가 설정되지 않았습니다.") }),
    ]);
    setScraps(result.scraps);
    setHasMore(result.hasMore);
    setLoadError(result.error ? "스크랩을 불러오지 못했습니다. 다시 시도해주세요." : "");
    const nextIndex = new Map<string, string>();
    for (const item of indexResult.data ?? []) nextIndex.set(item.article_key, item.id);
    for (const item of result.scraps) nextIndex.set(item.article_key, item.id);
    setScrapIndex(nextIndex);
  }, []);

  const loadMoreScraps = useCallback(async () => {
    if (!user || loadInFlight.current || (!hasMore && scraps.length > 0)) return;
    const last = scraps.at(-1);

    loadInFlight.current = true;
    setLoadingMore(true);
    setLoadError("");
    try {
      const result = await fetchScrapsPage(
        user.id,
        last ? { createdAt: last.created_at, id: last.id } : null
      );
      if (result.error) {
        setLoadError("스크랩을 더 불러오지 못했습니다. 다시 시도해주세요.");
        return;
      }
      setScraps((current) => {
        const knownIds = new Set(current.map((scrap) => scrap.id));
        return [...current, ...result.scraps.filter((scrap) => !knownIds.has(scrap.id))];
      });
      setScrapIndex((current) => {
        const next = new Map(current);
        for (const scrap of result.scraps) next.set(scrap.article_key, scrap.id);
        return next;
      });
      setHasMore(result.hasMore);
    } finally {
      loadInFlight.current = false;
      setLoadingMore(false);
    }
  }, [user, hasMore, scraps]);

  useEffect(() => {
    if (!supabase) {
      return;
    }

    let active = true;
    supabase.auth.getUser().then(async ({ data }) => {
      if (!active) return;
      setUser(data.user);
      if (data.user) await loadScraps(data.user.id);
      if (active) setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      const nextUser = session?.user ?? null;
      setUser(nextUser);
      if (nextUser) {
        setLoading(true);
        void loadScraps(nextUser.id).finally(() => setLoading(false));
      }
      else {
        setScraps([]);
        setHasMore(false);
        setLoadError("");
        setScrapIndex(new Map());
      }
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [loadScraps]);

  const toggleScrap = useCallback(async (draft: NewsScrapDraft) => {
    if (!supabase || !user) return "login" as const;
    const existingId = scrapIndex.get(draft.article_key);

    if (existingId) {
      const { error } = await supabase.from("news_scraps").delete().eq("id", existingId);
      if (error) throw error;
      setScraps((current) => current.filter((scrap) => scrap.id !== existingId));
      setScrapIndex((current) => {
        const next = new Map(current);
        next.delete(draft.article_key);
        return next;
      });
      return "removed" as const;
    }

    const { data, error } = await supabase
      .from("news_scraps")
      .insert({ ...draft, user_id: user.id })
      .select("*")
      .single();
    if (error) throw error;
    setScraps((current) => [data as NewsScrap, ...current]);
    setScrapIndex((current) => new Map(current).set(draft.article_key, (data as NewsScrap).id));
    return "saved" as const;
  }, [scrapIndex, user]);

  const signIn = useCallback(async (email: string) => {
    if (!supabase) return "Supabase가 설정되지 않았습니다.";
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/scraps` },
    });
    return error?.message ?? null;
  }, []);

  const verifyOtp = useCallback(async (email: string, token: string) => {
    if (!supabase) return "Supabase가 설정되지 않았습니다.";
    const { error } = await supabase.auth.verifyOtp({
      email,
      token,
      type: "email",
    });
    return error?.message ?? null;
  }, []);

  const signOut = useCallback(async () => {
    await supabase?.auth.signOut();
  }, []);

  return (
    <ScrapContext.Provider value={{
      user,
      scraps,
      loading,
      loadingMore,
      hasMore,
      loadError,
      loadMoreScraps,
      isScrapped: (articleKey) => scrapIndex.has(articleKey),
      toggleScrap,
      signIn,
      verifyOtp,
      signOut,
    }}>
      {children}
    </ScrapContext.Provider>
  );
}

export function useScraps(): ScrapContextValue {
  const context = useContext(ScrapContext);
  if (!context) throw new Error("useScraps must be used within ScrapProvider");
  return context;
}
