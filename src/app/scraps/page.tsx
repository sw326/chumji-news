"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import MainTabs from "@/components/MainTabs";
import { useScraps } from "@/components/ScrapProvider";
import { CATEGORY_LABELS } from "@/lib/types";

export default function ScrapsPage() {
  const { user, scraps, loading, signIn, verifyOtp, signOut, toggleScrap } = useScraps();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [codeSent, setCodeSent] = useState(false);
  const [token, setToken] = useState("");

  async function handleSignIn(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    const error = await signIn(email);
    if (!error) setCodeSent(true);
    setMessage(error ?? "이메일로 받은 8자리 인증코드를 입력해주세요.");
    setSending(false);
  }

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    const error = await verifyOtp(email, token.trim());
    setMessage(error ?? "로그인되었습니다.");
    setSending(false);
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-card-border bg-background/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
          <h1 className="text-xl font-bold tracking-tight">스크랩</h1>
          <MainTabs active="scraps" />
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl px-4 py-6">
        {loading && <p className="py-10 text-center text-sm text-muted">스크랩을 불러오는 중입니다.</p>}

        {!loading && !user && (
          <section className="rounded-xl border border-card-border bg-card p-5">
            <h2 className="font-semibold">이메일로 로그인</h2>
            <p className="mt-1 text-sm leading-relaxed text-muted">Telegram 화면을 벗어나지 않고 이메일 인증코드를 입력하면 이 브라우저에 로그인이 유지됩니다.</p>
            {!codeSent ? <form onSubmit={handleSignIn} className="mt-4 flex gap-2">
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="이메일 주소"
                className="min-w-0 flex-1 rounded-lg border border-card-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button disabled={sending} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {sending ? "전송 중" : "인증코드 받기"}
              </button>
            </form> : <form onSubmit={handleVerify} className="mt-4 flex gap-2">
              <input
                inputMode="numeric"
                autoComplete="one-time-code"
                required
                minLength={8}
                maxLength={8}
                value={token}
                onChange={(event) => setToken(event.target.value.replace(/\D/g, ""))}
                placeholder="8자리 인증코드"
                className="min-w-0 flex-1 rounded-lg border border-card-border bg-background px-3 py-2 text-sm tracking-widest outline-none focus:border-accent"
              />
              <button disabled={sending || token.length !== 8} className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {sending ? "확인 중" : "로그인"}
              </button>
            </form>}
            {message && <p className="mt-3 text-xs text-muted">{message}</p>}
          </section>
        )}

        {!loading && user && (
          <>
            <div className="mb-5 flex items-center justify-between text-xs text-muted">
              <span>{scraps.length}개 저장됨</span>
              <button onClick={() => void signOut()} className="hover:text-accent">로그아웃</button>
            </div>

            {scraps.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted">뉴스 카드의 북마크 버튼으로 기사를 저장해보세요.</p>
            ) : (
              <div className="space-y-3">
                {scraps.map((scrap) => (
                  <article key={scrap.id} className="relative rounded-xl border border-card-border bg-card p-4 pr-12">
                    <button
                      type="button"
                      aria-label="스크랩 삭제"
                      onClick={() => void toggleScrap({
                        article_key: scrap.article_key,
                        post_id: scrap.post_id,
                        post_date: scrap.post_date,
                        category: scrap.category,
                        emoji: scrap.emoji,
                        title: scrap.title,
                        description: scrap.description,
                        source_text: scrap.source_text,
                        source_url: scrap.source_url,
                      })}
                      className="absolute right-3 top-3 rounded-md p-2 text-accent hover:bg-accent/10"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="17" height="17" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" strokeWidth="2"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z" /></svg>
                    </button>
                    <div className="mb-2 flex items-center gap-2 text-xs text-muted">
                      <span>{CATEGORY_LABELS[scrap.category]}</span>
                      <span>{scrap.post_date}</span>
                    </div>
                    <h2 className="text-sm font-semibold leading-snug">{scrap.emoji && `${scrap.emoji} `}{scrap.title}</h2>
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
