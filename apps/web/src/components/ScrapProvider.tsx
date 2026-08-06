"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";
import type { NewsScrap, NewsScrapDraft } from "@/lib/types";

interface ScrapContextValue {
  user: User | null;
  scraps: NewsScrap[];
  loading: boolean;
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

  const loadScraps = useCallback(async (userId: string) => {
    if (!supabase) return;
    const { data } = await supabase
      .from("news_scraps")
      .select("*")
      .eq("user_id", userId)
      .order("created_at", { ascending: false });
    setScraps((data ?? []) as NewsScrap[]);
  }, []);

  useEffect(() => {
    if (!supabase) return;
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
      if (nextUser) void loadScraps(nextUser.id);
      else setScraps([]);
    });

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [loadScraps]);

  const toggleScrap = useCallback(async (draft: NewsScrapDraft) => {
    if (!supabase || !user) return "login" as const;
    const existing = scraps.find((scrap) => scrap.article_key === draft.article_key);

    if (existing) {
      const { error } = await supabase.from("news_scraps").delete().eq("id", existing.id);
      if (error) throw error;
      setScraps((current) => current.filter((scrap) => scrap.id !== existing.id));
      return "removed" as const;
    }

    const { data, error } = await supabase
      .from("news_scraps")
      .insert({ ...draft, user_id: user.id })
      .select("*")
      .single();
    if (error) throw error;
    setScraps((current) => [data as NewsScrap, ...current]);
    return "saved" as const;
  }, [scraps, user]);

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
    const { error } = await supabase.auth.verifyOtp({ email, token, type: "email" });
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
      isScrapped: (articleKey) => scraps.some((scrap) => scrap.article_key === articleKey),
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
