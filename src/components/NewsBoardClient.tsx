"use client";

import { useState, useMemo } from "react";
import { NewsPost, Category } from "@/lib/types";
import { groupByDate } from "@/lib/data";
import CategoryTabs from "./CategoryTabs";
import NewsCard from "./NewsCard";
import NewsContent from "./NewsContent";
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
  posts: NewsPost[];
}

export default function NewsBoardClient({ posts }: NewsBoardClientProps) {
  const [filter, setFilter] = useState<Category | "all">("all");
  const [selectedPost, setSelectedPost] = useState<NewsPost | null>(null);

  const filtered = useMemo(
    () => (filter === "all" ? posts : posts.filter((p) => p.category === filter)),
    [posts, filter]
  );

  const grouped = useMemo(() => groupByDate(filtered), [filtered]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-4 py-3">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-xl font-bold">🐟 참치뉴스</h1>
          </div>
          <CategoryTabs selected={filter} onChange={setFilter} />
        </div>
      </header>

      {/* Content area: split on desktop, stacked on mobile */}
      <div className="flex-1 mx-auto w-full max-w-7xl lg:flex lg:gap-0">
        {/* Left: card list */}
        <div className="lg:w-[380px] lg:shrink-0 lg:border-r lg:border-card-border lg:overflow-y-auto lg:h-[calc(100vh-108px)] p-4 space-y-6">
          {Array.from(grouped.entries()).map(([date, datePosts]) => (
            <section key={date}>
              <h2 className="text-sm font-semibold text-muted mb-3">
                {formatDateLabel(date)}
              </h2>
              <div className="space-y-2">
                {datePosts.map((post) => (
                  <NewsCard
                    key={post.id}
                    post={post}
                    selected={selectedPost?.id === post.id}
                    onClick={() => setSelectedPost(post)}
                  />
                ))}
              </div>
            </section>
          ))}
          {filtered.length === 0 && (
            <p className="text-center text-muted py-10">
              해당 카테고리에 뉴스가 없습니다.
            </p>
          )}
        </div>

        {/* Right: content viewer */}
        <div className="flex-1 lg:overflow-y-auto lg:h-[calc(100vh-108px)] p-4 lg:p-8">
          <NewsContent post={selectedPost} />
        </div>
      </div>

      <ScrollToTop />
    </div>
  );
}
