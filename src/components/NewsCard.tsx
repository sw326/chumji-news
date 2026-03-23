import { NewsPost, CATEGORY_LABELS } from "@/lib/types";

interface NewsCardProps {
  post: NewsPost;
  selected?: boolean;
  onClick?: () => void;
}

export default function NewsCard({ post, selected, onClick }: NewsCardProps) {
  const title = extractTitle(post.content);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-4 transition-all ${
        selected
          ? "border-accent bg-accent-light ring-1 ring-accent"
          : "border-card-border bg-card hover:border-accent/50 hover:shadow-sm"
      }`}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="inline-block rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
          {CATEGORY_LABELS[post.category]}
        </span>
      </div>
      <h3 className="font-semibold text-sm leading-snug line-clamp-2">
        {title}
      </h3>
    </button>
  );
}

function extractTitle(content: string): string {
  const match = content.match(/^#\s+(.+)$/m);
  return match ? match[1] : content.slice(0, 60);
}
