"use client";

import { FormEvent, useMemo, useState } from "react";
import Link from "next/link";
import MainTabs from "@/components/MainTabs";
import { useScraps } from "@/components/ScrapProvider";
import { CATEGORIES, CATEGORY_LABELS, type Category } from "@/lib/types";

function authErrorMessage(error: string, verify = false) {
  if (/(rate|limit|too many)/i.test(error)) {
    return "이메일 발송 한도에 걸렸습니다. 이미 받은 최신 8자리 코드를 입력해주세요.";
  }
  return verify
    ? "인증코드가 잘못되었거나 만료됐습니다. 최신 8자리 코드를 확인해주세요."
    : "인증코드를 보내지 못했습니다. 잠시 후 다시 시도해주세요.";
}

export default function ScrapsPage() {
  const { user, scraps, loading, signIn, verifyOtp, signOut, toggleScrap } = useScraps();
  const [email, setEmail] = useState("");
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<Category | "all">("all");

  const visibleScraps = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("ko-KR");
    return scraps.filter((scrap) => {
      if (category !== "all" && scrap.category !== category) return false;
      if (!normalized) return true;
      return [scrap.title, scrap.description, scrap.source_text]
        .join(" ")
        .toLocaleLowerCase("ko-KR")
        .includes(normalized);
    });
  }, [scraps, category, query]);

  async function handleSignIn(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    const error = await signIn(email);
    setMessage(error ? authErrorMessage(error) : "이메일로 받은 최신 8자리 인증코드를 입력해주세요.");
    setSending(false);
  }

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    const error = await verifyOtp(email, token);
    setMessage(error ? authErrorMessage(error, true) : "로그인되었습니다.");
    setSending(false);
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-4xl flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between">
          <h1 className="text-xl font-bold tracking-tight">스크랩</h1>
          <MainTabs active="scraps" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl px-4 py-6">
        {loading && <p className="py-10 text-center text-sm text-muted">스크랩을 불러오는 중입니다.</p>}

        {!loading && !user && (
          <section className="rounded-xl border border-card-border bg-card p-5">
            <h2 className="font-semibold">이메일로 로그인</h2>
            <p className="mt-1 text-sm text-muted">뉴스를 스크랩하려면 이메일 인증이 필요합니다.</p>
            <form onSubmit={handleSignIn} className="mt-4 flex gap-2">
              <input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="이메일 주소" className="min-w-0 flex-1 rounded-lg border border-card-border bg-background px-3 py-2 text-sm" />
              <button disabled={sending} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">인증코드 받기</button>
            </form>
            <form onSubmit={handleVerify} className="mt-3 flex gap-2">
              <input inputMode="numeric" required minLength={8} maxLength={8} value={token} onChange={(event) => setToken(event.target.value.replace(/\D/g, ""))} placeholder="8자리 인증코드" className="min-w-0 flex-1 rounded-lg border border-card-border bg-background px-3 py-2 text-sm tracking-widest" />
              <button disabled={sending || token.length !== 8} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">로그인</button>
            </form>
            {message && <p className="mt-3 text-xs text-muted">{message}</p>}
          </section>
        )}

        {!loading && user && (
          <>
            <div className="mb-5 flex items-center justify-between text-xs text-muted">
              <span>{scraps.length}개 저장됨</span>
              <button onClick={() => void signOut()} className="hover:text-accent">로그아웃</button>
            </div>
            {scraps.length > 0 && (
              <section className="mb-5 flex flex-col gap-2 sm:flex-row">
                <input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="제목, 내용, 출처 검색" className="min-w-0 flex-1 rounded-lg border border-card-border bg-card px-3 py-2 text-sm" />
                <select value={category} onChange={(event) => setCategory(event.target.value as Category | "all")} className="rounded-lg border border-card-border bg-card px-3 py-2 text-sm">
                  <option value="all">모든 카테고리</option>
                  {CATEGORIES.filter((item) => scraps.some((scrap) => scrap.category === item)).map((item) => <option key={item} value={item}>{CATEGORY_LABELS[item]}</option>)}
                </select>
              </section>
            )}
            {visibleScraps.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted">{scraps.length ? "조건에 맞는 스크랩이 없습니다." : "뉴스 카드의 북마크 버튼으로 기사를 저장해보세요."}</p>
            ) : (
              <div className="space-y-3">
                {visibleScraps.map((scrap) => (
                  <article key={scrap.id} className="relative rounded-xl border border-card-border bg-card p-4 pr-12">
                    <button type="button" aria-label="스크랩 삭제" onClick={() => void toggleScrap({ article_key: scrap.article_key, post_id: scrap.post_id, post_date: scrap.post_date, category: scrap.category, emoji: scrap.emoji, title: scrap.title, description: scrap.description, source_text: scrap.source_text, source_url: scrap.source_url })} className="absolute right-3 top-3 rounded-md p-2 text-accent hover:bg-accent/10">
                      <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" /></svg>
                    </button>
                    <div className="mb-2 flex gap-2 text-xs text-muted"><span>{CATEGORY_LABELS[scrap.category]}</span><span>{scrap.post_date}</span></div>
                    <h2 className="text-sm font-semibold">{scrap.emoji && `${scrap.emoji} `}{scrap.title}</h2>
                    {scrap.description && <p className="mt-1.5 text-xs leading-relaxed text-muted">{scrap.description}</p>}
                    <div className="mt-3 flex gap-4 text-xs font-medium text-accent">
                      {scrap.source_url && <a href={scrap.source_url} target="_blank" rel="noopener noreferrer">원문 보기</a>}
                      <Link href={`/news/${scrap.post_date}/${scrap.category}`}>브리핑 보기</Link>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
