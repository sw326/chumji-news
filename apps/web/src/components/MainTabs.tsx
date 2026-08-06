import Link from "next/link";

interface MainTabsProps {
  active: "news" | "prices" | "scraps" | "market" | "alerts" | "operations";
}

export default function MainTabs({ active }: MainTabsProps) {
  return (
    <nav className="grid w-full grid-cols-3 gap-1.5 sm:grid-cols-6 md:w-auto" aria-label="주요 화면">
      <MainTab href="/" label="뉴스" active={active === "news"} />
      <MainTab href="/prices" label="가격" active={active === "prices"} />
      <MainTab href="/scraps" label="스크랩" active={active === "scraps"} />
      <MainTab href="/market" label="시장" active={active === "market"} />
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
      className={`flex min-h-11 items-center justify-center whitespace-nowrap rounded-md px-2 text-xs font-semibold transition-colors sm:px-3.5 ${
        active
          ? "bg-foreground text-background"
          : "border border-card-border bg-card text-muted hover:border-accent/40 hover:text-accent"
      }`}
    >
      {label}
    </Link>
  );
}
