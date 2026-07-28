import Link from "next/link";
import { NewsPost, CATEGORY_LABELS } from "@/lib/types";

interface NewsCardProps {
  post: NewsPost;
}

export default function NewsCard({ post }: NewsCardProps) {
  const { title, preview } = extractTitleAndPreview(post.content);
  const dateFormatted = formatDate(post.date);

  return (
    <Link
      href={`/news/${post.date}/${post.category}`}
      className="group block w-full text-left rounded-xl border border-card-border bg-card px-5 py-4 transition-all hover:border-accent/50 hover:shadow-md hover:shadow-accent/5 hover:-translate-y-0.5"
    >
      <div className="flex items-center gap-2 mb-2.5">
        <span className="inline-flex items-center rounded-md bg-accent/10 px-2 py-0.5 text-xs font-semibold text-accent tracking-wide">
          {CATEGORY_LABELS[post.category]}
        </span>
        <span className="text-xs text-muted">{dateFormatted}</span>
      </div>
      <h3 className="font-semibold text-sm leading-snug mb-1.5 group-hover:text-accent transition-colors line-clamp-2">
        {title}
      </h3>
      {preview && (
        <p className="text-xs text-muted leading-relaxed line-clamp-2">
          {preview}
        </p>
      )}
      <div className="mt-3 flex items-center gap-1 text-xs text-muted group-hover:text-accent transition-colors">
        <span>자세히 보기</span>
        <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M9 18l6-6-6-6" />
        </svg>
      </div>
    </Link>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.floor((today.getTime() - d.getTime()) / (1000 * 60 * 60 * 24));
  if (diff === 0) return "오늘";
  if (diff === 1) return "어제";
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function extractTitleAndPreview(content: string): { title: string; preview: string } {
  // Extract # heading as title
  const headingMatch = content.match(/^#\s+(.+)$/m);
  const title = headingMatch ? headingMatch[1] : content.slice(0, 60);

  // Try to find first article block (emoji + **bold** pattern)
  const articleMatch = content.match(/[^\n]*\*\*([^*]+)\*\*\n([^\n[]+)/m);
  if (articleMatch) {
    return { title, preview: articleMatch[2].trim().slice(0, 120) };
  }

  // Fallback: first paragraph after heading
  const lines = content.split("\n");
  for (const line of lines) {
    const cleaned = line.replace(/^#+\s*/, "").replace(/\*\*/g, "").trim();
    if (cleaned && !cleaned.startsWith("#") && !cleaned.startsWith("---") && cleaned.length > 20) {
      return { title, preview: cleaned.slice(0, 120) };
    }
  }

  return { title, preview: "" };
}
