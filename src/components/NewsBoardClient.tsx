"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { NewsPost, Category } from "@/lib/types";
import { groupByDate, PostsCursor } from "@/lib/data";
import { fetchPostsPage } from "@/lib/data";
import CategoryTabs from "./CategoryTabs";
import MainTabs from "./MainTabs";
import NewsCard from "./NewsCard";
import NewsCardSkeleton from "./NewsCardSkeleton";
import ScrollToTop from "./ScrollToTop";

const NEWS_STATE_KEY = "chumji-news:list-state:v1";
const NEWS_STATE_TTL = 30 * 60 * 1000;

interface SavedNewsState {
  savedAt: number;
  filter: Category | "all";
  posts: NewsPost[];
  cursor: PostsCursor | null;
  hasMore: boolean;
  scrollY: number;
}

function isFilter(value: unknown): value is Category | "all" {
  return value === "all" || ["news", "it", "trend", "realestate", "moltbook", "opendata", "system", "issues", "reddit"].includes(String(value));
}

function formatDateLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor(
    (today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24)
  );

  const weekday = ["일", "월", "화", "수", "목", "금", "토"][d.getDay()];
  const label = `${d.getMonth() + 1}/${d.getDate()} (${weekday})`;

  if (diff === 0) return `오늘 — ${label}`;
  if (diff === 1) return `어제 — ${label}`;
  return label;
}

interface NewsBoardClientProps {
  initialPosts: NewsPost[];
  initialHasMore: boolean;
  initialCursor: PostsCursor | null;
  initialError?: string;
}

export default function NewsBoardClient({
  initialPosts,
  initialHasMore,
  initialCursor,
  initialError,
}: NewsBoardClientProps) {
  const [filter, setFilter] = useState<Category | "all">("all");
  const [posts, setPosts] = useState<NewsPost[]>(initialPosts);
  const [cursor, setCursor] = useState<PostsCursor | null>(initialCursor);
  const [hasMore, setHasMore] = useState(initialError ? true : initialHasMore);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState(initialError ? "뉴스를 불러오지 못했습니다. 다시 시도해주세요." : "");
  const [restored, setRestored] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const requestSequence = useRef(0);
  const requestInFlight = useRef(false);

  // 상세 화면에서 돌아올 때 필터, 로드된 페이지, 스크롤 위치를 함께 복원한다.
  useEffect(() => {
    let cancelled = false;

    async function restoreState() {
      try {
        const requestedValue = new URLSearchParams(window.location.search).get("category");
        const requestedFilter = isFilter(requestedValue) ? requestedValue : null;
        const raw = sessionStorage.getItem(NEWS_STATE_KEY);
        if (raw) {
          const saved = JSON.parse(raw) as SavedNewsState;
          if (
            Date.now() - saved.savedAt < NEWS_STATE_TTL &&
            isFilter(saved.filter) &&
            Array.isArray(saved.posts) &&
            (!requestedFilter || requestedFilter === saved.filter)
          ) {
            setFilter(saved.filter);
            setPosts(saved.posts);
            setCursor(saved.cursor);
            setHasMore(saved.hasMore);
            requestAnimationFrame(() => {
              requestAnimationFrame(() => window.scrollTo({ top: saved.scrollY }));
            });
            return;
          }
          sessionStorage.removeItem(NEWS_STATE_KEY);
        }

        if (isFilter(requestedFilter) && requestedFilter !== "all") {
          const result = await fetchPostsPage(null, requestedFilter);
          if (cancelled) return;
          if (result.error) setLoadError("뉴스를 불러오지 못했습니다. 다시 시도해주세요.");
          setFilter(requestedFilter);
          setPosts(result.posts);
          setHasMore(result.hasMore);
          setCursor(result.nextCursor);
        }
      } catch {
        sessionStorage.removeItem(NEWS_STATE_KEY);
      } finally {
        if (!cancelled) setRestored(true);
      }
    }

    void restoreState();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!restored) return;

    let frame = 0;
    const saveState = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const state: SavedNewsState = {
          savedAt: Date.now(),
          filter,
          posts,
          cursor,
          hasMore,
          scrollY: window.scrollY,
        };
        try {
          sessionStorage.setItem(NEWS_STATE_KEY, JSON.stringify(state));
        } catch {
          // Storage may be unavailable or full; navigation still works via history.
        }
      });
    };

    saveState();
    window.addEventListener("scroll", saveState, { passive: true });
    window.addEventListener("pagehide", saveState);
    return () => {
      window.removeEventListener("scroll", saveState);
      window.removeEventListener("pagehide", saveState);
      saveState();
    };
  }, [restored, filter, posts, cursor, hasMore]);

  // 카테고리 변경 시 리셋 + 첫 페이지 로드
  const handleFilterChange = useCallback(async (cat: Category | "all") => {
    const requestId = ++requestSequence.current;
    requestInFlight.current = true;
    setFilter(cat);
    setLoadError("");
    window.scrollTo({ top: 0 });
    const nextUrl = cat === "all" ? "/" : `/?category=${cat}`;
    window.history.replaceState({ ...window.history.state }, "", nextUrl);
    setLoading(true);
    setPosts([]);
    setCursor(null);
    setHasMore(true);
    try {
      const result = await fetchPostsPage(null, cat);
      if (requestId !== requestSequence.current) return;
      if (result.error) {
        setLoadError("뉴스를 불러오지 못했습니다. 다시 시도해주세요.");
        setHasMore(true);
        return;
      }
      setPosts(result.posts);
      setHasMore(result.hasMore);
      setCursor(result.nextCursor);
    } finally {
      if (requestId === requestSequence.current) {
        requestInFlight.current = false;
        setLoading(false);
      }
    }
  }, []);

  // 다음 페이지 로드
  const loadMore = useCallback(async () => {
    if (requestInFlight.current || !hasMore) return;
    const requestId = ++requestSequence.current;
    requestInFlight.current = true;
    setLoadError("");
    setLoading(true);
    try {
      const result = await fetchPostsPage(cursor, filter);
      if (requestId !== requestSequence.current) return;
      if (result.error) {
        setLoadError("뉴스를 더 불러오지 못했습니다. 다시 시도해주세요.");
        return;
      }
      setPosts((prev) => [...prev, ...result.posts]);
      setHasMore(result.hasMore);
      setCursor(result.nextCursor);
    } finally {
      if (requestId === requestSequence.current) {
        requestInFlight.current = false;
        setLoading(false);
      }
    }
  }, [hasMore, cursor, filter]);

  // IntersectionObserver — sentinel 감지
  useEffect(() => {
    if (!restored) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMore, restored]);

  const grouped = useMemo(() => groupByDate(posts), [posts]);

  return (
    <div className="flex flex-col min-h-full">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-2xl px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-bold tracking-tight">뉴스 브리핑</h1>
            <MainTabs active="news" />
          </div>
          <CategoryTabs selected={filter} onChange={handleFilterChange} />
        </div>
      </header>

      {/* Card list */}
      <main className="mx-auto w-full max-w-2xl px-4 py-6 space-y-8">
        {Array.from(grouped.entries()).map(([date, datePosts]) => (
          <section key={date} className="lazy-section">
            <h2 className="text-xs font-semibold text-muted uppercase tracking-wider mb-3 flex items-center gap-2">
              <span className="h-px flex-1 bg-card-border" />
              {formatDateLabel(date)}
              <span className="h-px flex-1 bg-card-border" />
            </h2>
            <div className="space-y-3">
              {datePosts.map((post) => (
                <NewsCard key={post.id} post={post} />
              ))}
            </div>
          </section>
        ))}

        {/* 스켈레톤 로더 */}
        {loading && (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <NewsCardSkeleton key={i} />
            ))}
          </div>
        )}

        {loadError && !loading && (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <p className="text-sm text-muted">{loadError}</p>
            <button type="button" onClick={() => void loadMore()} className="rounded-lg border border-card-border bg-card px-4 py-2 text-xs font-semibold text-accent hover:border-accent/50">
              다시 시도
            </button>
          </div>
        )}

        {/* 더 이상 없음 */}
        {!hasMore && posts.length > 0 && !loading && (
          <p className="text-center text-xs text-muted py-4">
            모든 브리핑을 불러왔습니다
          </p>
        )}

        {/* 빈 상태 */}
        {!loading && posts.length === 0 && (
          <p className="text-center text-muted py-10">
            해당 카테고리에 뉴스가 없습니다.
          </p>
        )}

        {/* IntersectionObserver 트리거 */}
        {hasMore && !loadError && <div ref={sentinelRef} className="h-1" />}
      </main>

      <ScrollToTop />
    </div>
  );
}
