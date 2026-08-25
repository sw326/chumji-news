import { getPost } from "@/lib/data";
import { Category, CATEGORIES, CATEGORY_LABELS } from "@/lib/types";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import DetailBackLink from "@/components/DetailBackLink";
import Link from "next/link";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

interface PageProps {
  params: Promise<{ date: string; cat: string }>;
  searchParams: Promise<{ from?: string }>;
}

export async function generateMetadata({ params }: PageProps) {
  const { date, cat } = await params;
  const category = cat as Category;
  const label = CATEGORY_LABELS[category] ?? cat;
  return {
    title: `${label} — ${date} | 뉴스`,
    description: `${date} ${label} 브리핑`,
  };
}

export default async function NewsPage({ params, searchParams }: PageProps) {
  const { date, cat } = await params;
  const { from } = await searchParams;
  const category = cat as Category;

  if (!CATEGORIES.includes(category)) {
    notFound();
  }

  const post = await getPost(date, category);

  if (!post) {
    return (
      <main className="flex flex-col items-center justify-center min-h-screen gap-4">
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
        <DetailBackLink from={from} />
      </nav>
      <div className="text-xs text-muted mb-4">
        {date} · {CATEGORY_LABELS[category]}
      </div>
      <article className="prose max-w-none">
        <MarkdownRenderer content={post.content} postId={post.id} postDate={post.date} category={post.category} />
      </article>
    </main>
  );
}
