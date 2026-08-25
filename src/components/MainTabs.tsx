import Link from "next/link";

interface MainTabsProps {
  active?: "news" | "scraps";
}

export default function MainTabs({ active }: MainTabsProps) {
  return (
    <nav className="flex shrink-0 items-center gap-1 sm:gap-1.5" aria-label="주요 화면">
      <MainTab href="/" label="뉴스" active={active === "news"} />
      <MainTab href="/scraps" label="스크랩" active={active === "scraps"} />
    </nav>
  );
}

function MainTab({
  href,
  label,
  active,
}: {
  href: string;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`inline-flex min-h-10 items-center justify-center whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors sm:px-3.5 ${
        active
          ? "bg-foreground text-background"
          : "border border-card-border bg-card text-muted hover:border-accent/40 hover:text-accent"
      }`}
    >
      {label}
    </Link>
  );
}
