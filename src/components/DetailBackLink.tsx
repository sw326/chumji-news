"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

interface DetailBackLinkProps {
  from?: string;
}

export default function DetailBackLink({ from }: DetailBackLinkProps) {
  const router = useRouter();
  const fromScraps = from === "scraps";

  if (!fromScraps) {
    return <BackLink href="/" label="뉴스 메인" />;
  }

  return (
    <button
      type="button"
      onClick={() => router.back()}
      className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
    >
      <BackIcon />
      스크랩으로 돌아가기
    </button>
  );
}

function BackLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
    >
      <BackIcon />
      {label}
    </Link>
  );
}

function BackIcon() {
  return (
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
      aria-hidden="true"
    >
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}
