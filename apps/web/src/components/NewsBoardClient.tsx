"use client";

import { useState, useMemo, useEffect, useRef, useCallback } from "react";
import { NewsPost, Category } from "@/lib/types";
import { groupByDate } from "@/lib/data";
import { fetchPostsPage } from "@/lib/data";
import CategoryTabs from "./CategoryTabs";
import MainTabs from "./MainTabs";
import NewsCard from "./NewsCard";
import NewsCardSkeleton from "./NewsCardSkeleton";
import ScrollToTop from "./ScrollToTop";

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
}

export default function NewsBoardClient({
  initialPosts,
  initialHasMore,
}: NewsBoardClientProps) {
  const [filter, setFilter] = useState<Category | "all">("all");
  const [posts, setPosts] = useState<NewsPost[]>(initialPosts);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(initialHasMore);
  const [loading, setLoading] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // 카테고리 변경 시 리셋 + 첫 페이지 로드
  const handleFilterChange = useCallback(async (cat: Category | "all") => {
    setFilter(cat);
    setLoading(true);
    setPosts([]);
    setPage(0);
    const result = await fetchPostsPage(0, cat);
    setPosts(result.posts);
    setHasMore(result.hasMore);
    setPage(1);
    setLoading(false);
  }, []);

  // 다음 페이지 로드
  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return;
    setLoading(true);
    const result = await fetchPostsPage(page, filter);
    setPosts((prev) => [...prev, ...result.posts]);
    setHasMore(result.hasMore);
    setPage((p) => p + 1);
    setLoading(false);
  }, [loading, hasMore, page, filter]);

  // IntersectionObserver — sentinel 감지
  useEffect(() => {
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
  }, [loadMore]);

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
          <section key={date}>
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
        {hasMore && <div ref={sentinelRef} className="h-1" />}
      </main>

      <ScrollToTop />
    </div>
  );
}
