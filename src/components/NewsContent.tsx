import { NewsPost, CATEGORY_LABELS } from "@/lib/types";
import MarkdownRenderer from "./MarkdownRenderer";

interface NewsContentProps {
  post: NewsPost | null;
}

export default function NewsContent({ post }: NewsContentProps) {
  if (!post) {
    return (
      <div className="flex items-center justify-center h-full text-muted">
        <p className="text-center">
          <span className="block text-4xl mb-3">🔔</span>
          뉴스를 선택해주세요
        </p>
      </div>
    );
  }

  return (
    <article className="max-w-2xl mx-auto w-full overflow-x-hidden">
      <div className="mb-4 flex items-center gap-2">
        <span className="inline-flex items-center rounded-full bg-accent/10 px-3 py-1 text-sm font-semibold text-accent">
          {CATEGORY_LABELS[post.category]}
        </span>
        <span className="text-xs text-muted">{post.date}</span>
      </div>
      <MarkdownRenderer content={post.content} />
    </article>
  );
}
