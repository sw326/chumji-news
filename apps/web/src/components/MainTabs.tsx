import Link from "next/link";

interface MainTabsProps {
  active: "news" | "prices" | "alerts" | "operations";
}

export default function MainTabs({ active }: MainTabsProps) {
  return (
    <nav className="flex items-center gap-1.5" aria-label="주요 화면">
      <MainTab href="/" label="뉴스" active={active === "news"} />
      <MainTab href="/prices" label="가격" active={active === "prices"} />
      <MainTab href="/alerts" label="알림" active={active === "alerts"} />
      <MainTab href="/operations" label="운영" active={active === "operations"} />
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
      className={`whitespace-nowrap rounded-md px-3.5 py-1.5 text-xs font-semibold transition-colors ${
        active
          ? "bg-foreground text-background"
          : "border border-card-border bg-card text-muted hover:border-accent/40 hover:text-accent"
      }`}
    >
      {label}
    </Link>
  );
}
