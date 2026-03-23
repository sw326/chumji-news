import { getPost } from "@/lib/data";
import { Category, CATEGORIES, CATEGORY_LABELS } from "@/lib/types";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import Link from "next/link";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ date: string; cat: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { date, cat } = await params;
  const category = cat as Category;
  const label = CATEGORY_LABELS[category] ?? cat;
  return {
    title: `${label} — ${date} | 참치뉴스`,
    description: `${date} ${label} 브리핑`,
  };
}

export default async function NewsPage({ params }: PageProps) {
  const { date, cat } = await params;
  const category = cat as Category;

  if (!CATEGORIES.includes(category)) {
    return (
      <main className="flex items-center justify-center min-h-screen">
        <p className="text-muted">잘못된 카테고리입니다.</p>
      </main>
    );
  }

  const post = await getPost(date, category);

  if (!post) {
    return (
      <main className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-4xl">🐟</p>
        <p className="text-muted">해당 뉴스를 찾을 수 없습니다.</p>
        <Link href="/" className="text-accent hover:underline text-sm">
          메인으로 돌아가기
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <nav className="mb-6">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
          참치뉴스 메인
        </Link>
      </nav>
      <div className="text-xs text-muted mb-4">
        {date} · {CATEGORY_LABELS[category]}
      </div>
      <article className="prose max-w-none">
        <MarkdownRenderer content={post.content} />
      </article>
    </main>
  );
}
