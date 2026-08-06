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
                <p className="mt-2 text-xs leading-5 text-muted">{signal.detail}</p>
                <p className="mt-2 text-[11px] leading-4 text-muted">{signal.comparison_basis}</p>
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
        <div className="overflow-x-auto">
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
                  <td className="p-3">{item.quality.score}/{item.quality.maximum} · {item.quality.grade}</td>
                  <td className="p-3">{item.reexport_signal ?? "산출 안 함"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-lg border border-card-border bg-card p-5 shadow-sm">
        <h2 className="text-sm font-semibold text-foreground">검수 결과</h2>
        <p className="mt-3 text-sm font-semibold">중국 GACC · {gate.china_manual_check.status}</p>
        <p className="mt-1 text-sm leading-6 text-muted">{gate.china_manual_check.instruction}</p>
        {gate.warnings.length > 0 && <ul className="mt-4 list-disc space-y-2 pl-5 text-sm leading-6 text-muted">{gate.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
      </section>
    </main>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <article className="rounded-lg border border-card-border bg-card p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p><p className="mt-2 text-xl font-semibold text-foreground">{value}</p><p className="mt-1 text-xs text-muted">{detail}</p></article>;
}
