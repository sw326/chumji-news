import MainTabs from "@/components/MainTabs";
import { getRecentPriceSnapshots } from "@/lib/data";
import Link from "next/link";

export const metadata = {
  title: "신선식품 가격 | 뉴스 브리핑",
  description: "가락시장 도매와 KAMIS 소매 가격 스냅샷",
};

function formatDateLabel(date: string) {
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor(
    (today.getTime() - parsed.getTime()) / (1000 * 60 * 60 * 24)
  );
  const weekday = ["일", "월", "화", "수", "목", "금", "토"][parsed.getDay()];
  const label = `${parsed.getMonth() + 1}/${parsed.getDate()} (${weekday})`;

  if (diff === 0) return `오늘 — ${label}`;
  if (diff === 1) return `어제 — ${label}`;
  return label;
}

function formatCardDate(date: string) {
  const parsed = new Date(`${date}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return date;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor(
    (today.getTime() - parsed.getTime()) / (1000 * 60 * 60 * 24)
  );
  if (diff === 0) return "오늘";
  if (diff === 1) return "어제";
  return `${parsed.getMonth() + 1}/${parsed.getDate()}`;
}

const PRICE_CATEGORIES = [
  { key: "all", label: "전체" },
  { key: "vegetables", label: "채소" },
] as const;

type PriceCategoryKey = (typeof PRICE_CATEGORIES)[number]["key"];

function titleFromContent(content: string) {
  return (
    content
      .split("\n")
      .find((line) => line.startsWith("# "))
      ?.replace(/^#\s+/, "")
      .trim() || "신선식품 가격 스냅샷"
  );
}

function categoryFromContent(content: string): Exclude<PriceCategoryKey, "all"> {
  if (content.includes("- 분류: 채소")) return "vegetables";
  return "vegetables";
}

function categoryLabelFromContent(content: string) {
  const category = categoryFromContent(content);
  return PRICE_CATEGORIES.find((item) => item.key === category)?.label ?? "가격";
}

function previewFromContent(content: string) {
  const lines = content.split("\n").map((line) => line.trim());
  const basis = lines.find((line) => line.startsWith("- 기준:"));
  const items = lines.find((line) => line.startsWith("- 품목:"));
  return [basis?.replace("- 기준: ", ""), items?.replace("- 품목: ", "")]
    .filter(Boolean)
    .join(" · ");
}

interface PricesPageProps {
  searchParams: Promise<{ category?: string }>;
}

export default async function PricesPage({ searchParams }: PricesPageProps) {
  const { category } = await searchParams;
  const selectedCategory: PriceCategoryKey =
    category === "vegetables" ? "vegetables" : "all";
  const allPosts = await getRecentPriceSnapshots(50);
  const posts =
    selectedCategory === "all"
      ? allPosts
      : allPosts.filter((post) => categoryFromContent(post.content) === selectedCategory);
  const latest = posts[0];
  const grouped = new Map<string, typeof posts>();
  for (const post of posts) {
    const existing = grouped.get(post.date) ?? [];
    existing.push(post);
    grouped.set(post.date, existing);
  }

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-2xl px-4 py-3">
          <div className="mb-3 flex items-center justify-between">
            <h1 className="text-xl font-bold tracking-tight">신선식품 가격</h1>
            <MainTabs active="prices" />
          </div>
          <div className="flex gap-1.5 overflow-x-auto pb-1">
            {PRICE_CATEGORIES.map((priceCategory) => {
              const active = selectedCategory === priceCategory.key;
              const href =
                priceCategory.key === "all"
                  ? "/prices"
                  : `/prices?category=${priceCategory.key}`;
              return (
                <Link
                  key={priceCategory.key}
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`whitespace-nowrap rounded-md px-3.5 py-1.5 text-xs font-medium transition-colors ${
                    active
                      ? "bg-accent text-white"
                      : "border border-card-border bg-card text-muted hover:border-accent/40 hover:text-accent"
                  }`}
                >
                  {priceCategory.label}
                </Link>
              );
            })}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl flex-1 space-y-8 px-4 py-6">
        {latest && (
          <div className="text-xs text-muted">
            최신 저장: {formatCardDate(latest.date)}
          </div>
        )}

        {posts.length > 0 ? (
          Array.from(grouped.entries()).map(([date, datePosts]) => (
            <section key={date}>
              <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
                <span className="h-px flex-1 bg-card-border" />
                {formatDateLabel(date)}
                <span className="h-px flex-1 bg-card-border" />
              </h2>
              <div className="space-y-3">
                {datePosts.map((post) => {
                  const title = titleFromContent(post.content);
                  const preview = previewFromContent(post.content);
                  return (
                    <Link
                      key={post.id}
                      href={`/prices/${post.date}?from=prices`}
                      scroll={false}
                      className="group block w-full rounded-xl border border-card-border bg-card px-5 py-4 text-left transition-all hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-md hover:shadow-accent/5"
                    >
                      <div className="mb-2.5 flex items-center gap-2">
                        <span className="inline-flex items-center rounded-md bg-accent/10 px-2 py-0.5 text-xs font-semibold tracking-wide text-accent">
                          {categoryLabelFromContent(post.content)}
                        </span>
                        <span className="text-xs text-muted">
                          {formatCardDate(post.date)}
                        </span>
                      </div>
                      <h3 className="mb-1.5 line-clamp-2 text-sm font-semibold leading-snug transition-colors group-hover:text-accent">
                        {title}
                      </h3>
                      {preview && (
                        <p className="line-clamp-2 text-xs leading-relaxed text-muted">
                          {preview}
                        </p>
                      )}
                      <div className="mt-3 flex items-center gap-1 text-xs text-muted transition-colors group-hover:text-accent">
                        <span>자세히 보기</span>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          width="12"
                          height="12"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth="2.5"
                        >
                          <path d="M9 18l6-6-6-6" />
                        </svg>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </section>
          ))
        ) : (
          <p className="py-10 text-center text-muted">
            해당 분류에 가격 그래프가 없습니다.
          </p>
        )}
      </main>
    </div>
  );
}
