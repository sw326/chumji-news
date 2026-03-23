import Link from "next/link";
import { NewsPost, CATEGORY_LABELS } from "@/lib/types";

interface NewsCardProps {
  post: NewsPost;
}

export default function NewsCard({ post }: NewsCardProps) {
  const title = extractTitle(post.content);

  return (
    <Link
      href={`/news/${post.date}/${post.category}`}
      className="block w-full text-left rounded-xl border border-card-border bg-card p-4 transition-all hover:border-accent/50 hover:shadow-sm"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-block rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
          {CATEGORY_LABELS[post.category]}
        </span>
      </div>
      <h3 className="font-semibold text-sm leading-snug line-clamp-2">
        {title}
      </h3>
    </Link>
  );
}

function extractTitle(content: string): string {
  // Try first **bold text** pattern
  const boldMatch = content.match(/\*\*(.+?)\*\*/);
  if (boldMatch) return boldMatch[1];
  // Fallback to # heading
  const headingMatch = content.match(/^#\s+(.+)$/m);
  return headingMatch ? headingMatch[1] : content.slice(0, 60);
}
