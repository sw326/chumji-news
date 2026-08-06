"use client";

import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import MainTabs from "@/components/MainTabs";
import { useScraps } from "@/components/ScrapProvider";
import { CATEGORIES, CATEGORY_LABELS, Category, NewsScrap, NewsScrapDraft } from "@/lib/types";

const OTP_COOLDOWN_KEY = "chumji-news:otp-cooldown-until";
const OTP_COOLDOWN_SECONDS = 60;

function authErrorMessage(error: string, action: "send" | "verify") {
  const normalized = error.toLowerCase();
  if (/(rate|limit|too many|over_email_send_rate_limit)/.test(normalized)) {
    return "이메일 발송 한도에 걸렸습니다. 재요청을 멈추고, 이미 받은 최신 8자리 코드를 입력해주세요.";
  }
  if (action === "verify" && /(expired|invalid|token|otp)/.test(normalized)) {
    return "인증코드가 잘못되었거나 만료됐습니다. 최신 8자리 코드를 확인해주세요.";
  }
  return action === "send"
    ? "인증코드를 보내지 못했습니다. 잠시 후 다시 시도해주세요."
    : "로그인하지 못했습니다. 이메일과 인증코드를 다시 확인해주세요.";
}

function toDraft(scrap: NewsScrap): NewsScrapDraft {
  return {
    article_key: scrap.article_key,
    post_id: scrap.post_id,
    post_date: scrap.post_date,
    category: scrap.category,
    emoji: scrap.emoji,
    title: scrap.title,
    description: scrap.description,
    source_text: scrap.source_text,
    source_url: scrap.source_url,
  };
}

export default function ScrapsPage() {
  const router = useRouter();
  const { user, scraps, loading, signIn, verifyOtp, signOut, toggleScrap } = useScraps();
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [token, setToken] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<Category | "all">("all");
  const [sort, setSort] = useState<"newest" | "oldest">("newest");
  const [deletedDraft, setDeletedDraft] = useState<NewsScrapDraft | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cooldownUntilRef = useRef(0);

  useEffect(() => () => {
    if (undoTimer.current) clearTimeout(undoTimer.current);
  }, []);

  useEffect(() => {
    function updateCooldown() {
      try {
        const storedUntil = Number(localStorage.getItem(OTP_COOLDOWN_KEY) || 0);
        if (storedUntil > cooldownUntilRef.current) cooldownUntilRef.current = storedUntil;
        const cooldownUntil = cooldownUntilRef.current;
        const remaining = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
        setCooldown(remaining);
        if (remaining === 0) {
          cooldownUntilRef.current = 0;
          localStorage.removeItem(OTP_COOLDOWN_KEY);
        }
      } catch {
        const remaining = Math.max(0, Math.ceil((cooldownUntilRef.current - Date.now()) / 1000));
        setCooldown(remaining);
      }
    }

    updateCooldown();
    const timer = window.setInterval(updateCooldown, 1000);
    return () => window.clearInterval(timer);
  }, []);

  function startCooldown() {
    const cooldownUntil = Date.now() + OTP_COOLDOWN_SECONDS * 1000;
    cooldownUntilRef.current = cooldownUntil;
    try {
      localStorage.setItem(OTP_COOLDOWN_KEY, String(cooldownUntil));
    } catch {
      // Some in-app browsers may block storage; keep the in-memory timer.
    }
    setCooldown(OTP_COOLDOWN_SECONDS);
  }

  const visibleScraps = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("ko-KR");
    return scraps
      .filter((scrap) => category === "all" || scrap.category === category)
      .filter((scrap) => {
        if (!normalizedQuery) return true;
        return [scrap.title, scrap.description, scrap.source_text]
          .join(" ")
          .toLocaleLowerCase("ko-KR")
          .includes(normalizedQuery);
      })
      .toSorted((a, b) => {
        const difference = new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
        return sort === "newest" ? difference : -difference;
      });
  }, [scraps, category, query, sort]);

  function openBriefing(scrap: NewsScrap) {
    router.push(`/news/${scrap.post_date}/${scrap.category}?from=scraps`, { scroll: false });
  }

  function handleCardKeyDown(event: KeyboardEvent<HTMLElement>, scrap: NewsScrap) {
    if (event.key === "Enter" && !(event.target as HTMLElement).closest("a, button, input, select")) {
      openBriefing(scrap);
    }
  }

  async function handleDelete(scrap: NewsScrap) {
    try {
      const draft = toDraft(scrap);
      await toggleScrap(draft);
      setDeletedDraft(draft);
      setActionMessage("");
      if (undoTimer.current) clearTimeout(undoTimer.current);
      undoTimer.current = setTimeout(() => setDeletedDraft(null), 6000);
    } catch {
      setActionMessage("스크랩을 삭제하지 못했습니다. 다시 시도해주세요.");
    }
  }

  async function handleUndo() {
    if (!deletedDraft) return;
    try {
      await toggleScrap(deletedDraft);
      setDeletedDraft(null);
      if (undoTimer.current) clearTimeout(undoTimer.current);
    } catch {
      setActionMessage("스크랩을 복원하지 못했습니다. 다시 시도해주세요.");
    }
  }

  async function handleSignIn(event: FormEvent) {
    event.preventDefault();
    if (sending || cooldown > 0) return;
    setSending(true);
    try {
      const error = await signIn(email);
      if (error) {
        if (/(rate|limit|too many|over_email_send_rate_limit)/i.test(error)) startCooldown();
        setMessage(authErrorMessage(error, "send"));
      } else {
        startCooldown();
        setMessage("이메일로 받은 최신 8자리 인증코드를 입력해주세요.");
      }
    } catch {
      setMessage("인증코드를 보내지 못했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setSending(false);
    }
  }

  async function handleVerify(event: FormEvent) {
    event.preventDefault();
    if (sending) return;
    setSending(true);
    try {
      const error = await verifyOtp(email, token.trim());
      setMessage(error ? authErrorMessage(error, "verify") : "로그인되었습니다.");
    } catch {
      setMessage("로그인하지 못했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setSending(false);
    }
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
            <form onSubmit={handleSignIn} className="mt-4 flex flex-col gap-2 sm:flex-row">
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="이메일 주소"
                className="min-w-0 flex-1 rounded-lg border border-card-border bg-background px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button disabled={sending || cooldown > 0} className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {sending ? "전송 중" : cooldown > 0 ? `${cooldown}초 후 재전송` : "인증코드 받기"}
              </button>
            </form>
            <form onSubmit={handleVerify} className="mt-3 flex flex-col gap-2 sm:flex-row">
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
              <button disabled={sending || token.length !== 8} className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                {sending ? "확인 중" : "로그인"}
              </button>
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
              <section className="mb-5 space-y-3" aria-label="스크랩 검색 및 필터">
                <div className="relative">
                  <svg className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
                  <input
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="제목, 내용, 출처 검색"
                    className="w-full rounded-lg border border-card-border bg-card py-2.5 pl-9 pr-3 text-sm outline-none focus:border-accent"
                  />
                </div>
                <div className="flex gap-2">
                  <select
                    value={category}
                    onChange={(event) => setCategory(event.target.value as Category | "all")}
                    aria-label="카테고리 필터"
                    className="min-w-0 flex-1 rounded-lg border border-card-border bg-card px-3 py-2 text-sm outline-none focus:border-accent"
                  >
                    <option value="all">모든 카테고리</option>
                    {CATEGORIES.filter((item) => scraps.some((scrap) => scrap.category === item)).map((item) => (
                      <option key={item} value={item}>{CATEGORY_LABELS[item]}</option>
                    ))}
                  </select>
                  <select
                    value={sort}
                    onChange={(event) => setSort(event.target.value as "newest" | "oldest")}
                    aria-label="저장일 정렬"
                    className="rounded-lg border border-card-border bg-card px-3 py-2 text-sm outline-none focus:border-accent"
                  >
                    <option value="newest">최신 저장순</option>
                    <option value="oldest">오래된 저장순</option>
                  </select>
                </div>
                {(query || category !== "all") && (
                  <p className="text-xs text-muted">검색 결과 {visibleScraps.length}개</p>
                )}
              </section>
            )}

            {scraps.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted">뉴스 카드의 북마크 버튼으로 기사를 저장해보세요.</p>
            ) : visibleScraps.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted">조건에 맞는 스크랩이 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {visibleScraps.map((scrap) => (
                  <article
                    key={scrap.id}
                    role="link"
                    tabIndex={0}
                    onClick={(event) => {
                      if (!(event.target as HTMLElement).closest("a, button, input, select")) openBriefing(scrap);
                    }}
                    onKeyDown={(event) => handleCardKeyDown(event, scrap)}
                    className="relative cursor-pointer rounded-xl border border-card-border bg-card p-4 pr-12 transition-colors hover:border-accent/40 focus:outline-none focus:ring-2 focus:ring-accent/40"
                  >
                    <button
                      type="button"
                      aria-label="스크랩 삭제"
                      onClick={() => void handleDelete(scrap)}
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
                      <Link href={`/news/${scrap.post_date}/${scrap.category}?from=scraps`} scroll={false}>브리핑 보기</Link>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </main>

      {deletedDraft && (
        <div className="fixed inset-x-4 bottom-5 z-50 mx-auto flex max-w-md items-center justify-between gap-4 rounded-xl border border-card-border bg-foreground px-4 py-3 text-sm text-background shadow-lg" role="status">
          <span className="truncate">스크랩을 삭제했습니다.</span>
          <button type="button" onClick={() => void handleUndo()} className="shrink-0 font-semibold text-accent">되돌리기</button>
        </div>
      )}
      {actionMessage && (
        <button type="button" onClick={() => setActionMessage("")} className="fixed inset-x-4 bottom-5 z-50 mx-auto max-w-md rounded-xl bg-red-600 px-4 py-3 text-left text-sm text-white shadow-lg">
          {actionMessage}
        </button>
      )}
    </div>
  );
}
