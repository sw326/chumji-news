import { NewsPost } from "@/lib/types";
import MarkdownRenderer from "./MarkdownRenderer";

interface NewsContentProps {
  post: NewsPost | null;
}

export default function NewsContent({ post }: NewsContentProps) {
  if (!post) {
    return (
      <div className="flex items-center justify-center h-full text-muted">
        <p className="text-center">
          <span className="block text-4xl mb-3">🐟</span>
          뉴스를 선택해주세요
        </p>
      </div>
    );
  }

  return (
    <article className="prose max-w-none">
      <MarkdownRenderer content={post.content} />
    </article>
  );
}
