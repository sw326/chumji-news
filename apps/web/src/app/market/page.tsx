import MainTabs from "@/components/MainTabs";
import MarketTrendChart from "@/components/MarketTrendChart";
import { getCathodeMarketBoard } from "@/lib/market-board-data";

export const revalidate = 300;

const COUNTRY_LABELS: Record<string, string> = {
  US: "미국",
  HU: "헝가리",
  PL: "폴란드",
  CN: "중국",
};

function money(value: number | null, currency = "USD"): string {
  if (value === null) return "비교 불가";
  return new Intl.NumberFormat("ko-KR", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

function percent(value: number | null): string {
  return value === null ? "비교 불가" : `${(value * 100).toFixed(1)}%`;
}

function period(value: string | null): string {
  if (!value) return "미확인";
  const normalized = value.replace("-", "");
  return `${normalized.slice(0, 4)}년 ${Number(normalized.slice(4, 6))}월`;
}

function reviewStatus(value: string): string {
  return ({
    verified: "검증 완료",
    "pending-one-time-verification": "수동 검증 대기",
    "review-required": "검토 필요",
    blocked: "차단",
  } as Record<string, string>)[value] ?? value;
}

function quality(value: string): string {
  return ({ high: "높음", medium: "보통", low: "낮음", insufficient: "불충분" } as Record<string, string>)[value] ?? value;
}

function reexport(value?: string): string {
  return ({ high: "높음", medium: "보통", low: "낮음", unknown: "미확인" } as Record<string, string>)[value ?? ""] ?? "산출 안 함";
}

export default async function MarketPage() {
  const board = await getCathodeMarketBoard();
  const korea = board.korea;
  const gate = board.review_gate;
  const signals = board.signals ?? [];

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-card-border pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            공식 통계 · 읽기 전용
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">
            양극재 시장판
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            국가별 최신 공개 월을 그대로 유지합니다. 기간·통화·품목 범위가
            다르면 신고 차액을 계산하지 않습니다.
          </p>
        </div>
        <MainTabs active="market" />
      </header>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="한국 누계 수출" value={money(korea.totals.export_usd)} detail={`${period(korea.period.start)}–${period(korea.period.end)}`} />
        <Metric label="전년 동기 증감" value={percent(korea.period_comparison.growth_rate)} detail={money(korea.period_comparison.change_usd)} />
        <Metric label="전용 코드 비중" value={percent(korea.classification_precision.dedicated_share)} detail={`광범위 코드 ${money(korea.classification_precision.broad_value_usd)}`} />
        <Metric label="검수 상태" value={gate.blockers.length ? "차단" : "검수 가능"} detail={`자동 출처 ${gate.automated_sources_complete ? "완료" : "미완료"}`} />
      </section>

      <section className="rounded-lg border border-card-border bg-card p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-foreground">데이터 기준월</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.entries(board.latest_periods).map(([source, value]) => (
            <span key={source} className="rounded-full border border-card-border bg-background px-3 py-1 text-xs font-semibold text-muted">
              {source === "korea_customs" ? "한국" : COUNTRY_LABELS[source] ?? source} · {period(value)}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-card-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">중국 GACC 수동 검수</h2>
            <p className="mt-1 text-sm font-semibold">{reviewStatus(gate.china_manual_check.status)}</p>
          </div>
          <span className="rounded-full border border-card-border bg-background px-3 py-1.5 text-xs font-semibold text-muted">대상 {period(gate.china_manual_check.target_period)}</span>
        </div>
        <p className="mt-3 text-sm leading-6 text-muted">{gate.china_manual_check.instruction}</p>
      </section>

      <section className="rounded-lg border border-card-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">이상 신호</h2>
            <p className="mt-1 text-xs leading-5 text-muted">원인 판정이 아닌 검토 후보입니다. 작은 기저값과 비교 불가능한 기간·통화·HS 범위는 제외합니다.</p>
          </div>
          <span className="rounded-full border border-card-border bg-background px-3 py-1 text-xs font-semibold text-muted">{signals.length}건</span>
        </div>
        {signals.length ? (
          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {signals.map((signal, index) => (
              <article key={`${signal.type}-${signal.country_code}-${signal.period}-${index}`} className="rounded-lg border border-card-border bg-background p-4">
                <div className="flex items-center justify-between gap-3">
                  <strong className="text-sm">{COUNTRY_LABELS[signal.country_code] ?? signal.country_code} · {signal.title}</strong>
                  <span className="text-xs text-muted">{signal.period}</span>
                </div>
                <p className="mt-2 text-xl font-semibold tabular-nums">{percent(signal.change_rate)}</p>
                <p className="mt-2 text-xs leading-5 text-muted">{signal.type === "mirror-gap" ? "동일 기간·USD 신고액을 확인하세요." : "동일 출처의 전년 동월과 비교한 검토 후보입니다."}</p>
              </article>
            ))}
          </div>
        ) : <p className="mt-4 text-sm text-muted">현재 임계값을 넘는 검토 신호가 없습니다.</p>}
      </section>

      <section className="rounded-lg border border-card-border bg-card p-4 shadow-sm">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-foreground">월별 추세</h2>
          <p className="mt-1 text-xs leading-5 text-muted">출처별 통화와 HS 범위를 유지한 작은 차트입니다. 서로 다른 통화·품목 범위는 한 축에 합치지 않습니다.</p>
        </div>
        <MarketTrendChart series={board.time_series ?? []} />
      </section>

      <section className="overflow-hidden rounded-lg border border-card-border bg-card shadow-sm">
        <div className="border-b border-card-border p-4">
          <h2 className="text-sm font-semibold text-foreground">상대국 공식 통계</h2>
        </div>
        <div className="grid gap-3 p-4 md:hidden">
          {board.partner_statistics.map((item) => (
            <article key={item.country_code} className="rounded-lg border border-card-border bg-background p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-base font-semibold">{COUNTRY_LABELS[item.country_code] ?? item.country_code}</h3>
                  <p className="mt-1 text-xs leading-5 text-muted">{item.source}</p>
                </div>
                <span className="text-xs font-semibold text-muted">{period(item.period)}</span>
              </div>
              <p className="mt-4 text-xs font-semibold text-muted">한국산 수입</p>
              <p className="mt-1 text-xl font-semibold tabular-nums">{money(item.value, item.currency)}</p>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-muted">전년 동기</dt><dd className="mt-1 font-semibold">{percent(item.growth_rate)}</dd></div>
                <div><dt className="text-xs text-muted">데이터 품질</dt><dd className="mt-1 font-semibold">{quality(item.quality.grade)} · {item.quality.score}/{item.quality.maximum}</dd></div>
                <div><dt className="text-xs text-muted">신고 차이</dt><dd className="mt-1 font-semibold">{item.mirror_comparable ? money(item.mirror_gap_usd) : "비교 불가"}</dd></div>
                <div><dt className="text-xs text-muted">재수출 신호</dt><dd className="mt-1 font-semibold">{reexport(item.reexport_signal)}</dd></div>
              </dl>
              <p className="mt-4 border-t border-card-border pt-3 text-xs leading-5 text-muted">{item.comparison_notice}</p>
            </article>
          ))}
        </div>
        <div className="hidden overflow-x-auto md:block">
          <table className="min-w-[920px] w-full text-sm">
            <thead className="bg-background text-left text-xs text-muted">
              <tr><th className="p-3">국가·출처</th><th className="p-3">기준월</th><th className="p-3 text-right">한국산 수입</th><th className="p-3">전년 동기</th><th className="p-3">한국 신고와 차이</th><th className="p-3">품질</th><th className="p-3">재수출 신호</th></tr>
            </thead>
            <tbody className="divide-y divide-card-border">
              {board.partner_statistics.map((item) => (
                <tr key={item.country_code}>
                  <td className="p-3"><strong>{COUNTRY_LABELS[item.country_code] ?? item.country_code}</strong><p className="mt-1 text-xs text-muted">{item.source}</p></td>
                  <td className="p-3">{period(item.period)}</td>
                  <td className="p-3 text-right font-semibold tabular-nums">{money(item.value, item.currency)}</td>
                  <td className="p-3">{percent(item.growth_rate)}</td>
                  <td className="p-3">{item.mirror_comparable ? money(item.mirror_gap_usd) : "비교 불가"}<p className="mt-1 max-w-xs text-xs text-muted">{item.comparison_notice}</p></td>
                  <td className="p-3">{item.quality.score}/{item.quality.maximum} · {quality(item.quality.grade)}</td>
                  <td className="p-3">{reexport(item.reexport_signal)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-card-border bg-card p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-foreground">해석 유의사항</h2>
        {gate.warnings.length > 0 && <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted">{gate.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
      </section>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-lg border border-card-border bg-card p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p><p className="mt-2 text-xl font-semibold text-foreground">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></article>;
}
