import MainTabs from "@/components/MainTabs";
import { getPriceSnapshot } from "@/lib/data";
import Link from "next/link";

interface PageProps {
  params: Promise<{ date: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { date } = await params;
  return {
    title: `신선식품 가격 — ${date} | 뉴스 브리핑`,
    description: `${date} 신선식품 가격 스냅샷`,
  };
}

export default async function PriceSnapshotPage({ params }: PageProps) {
  const { date } = await params;
  const post = await getPriceSnapshot(date);
  const safeDate = /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : "";

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto max-w-5xl px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold tracking-tight">신선식품 가격</h1>
            <MainTabs active="prices" />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-0 py-0 sm:px-4 sm:py-4">
        <nav className="px-4 py-3 sm:px-0">
          <Link
            href="/prices"
            className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
            >
              <path d="M15 18l-6-6 6-6" />
            </svg>
            가격 목록
          </Link>
        </nav>

        {post && safeDate ? (
          <>
            <div className="px-4 pb-3 text-xs text-muted sm:px-0">
              {post.date} · 그래프 페이지
            </div>
            <section className="sm:rounded-lg sm:border sm:border-card-border sm:bg-card sm:shadow-sm">
              <iframe
                title={`${post.date} 신선식품 가격 그래프`}
                src={`/fresh-food/${safeDate}/index.html`}
                className="block h-[calc(100dvh-110px)] w-full border-0 bg-white sm:h-[760px] sm:rounded-lg"
              />
            </section>
          </>
        ) : (
          <p className="mx-4 rounded-lg border border-card-border bg-card px-4 py-8 text-center text-sm text-muted sm:mx-0">
            해당 날짜의 가격 스냅샷을 찾을 수 없습니다.
          </p>
        )}
      </main>
    </div>
  );
}
