import { MarketTimeSeries } from "@/lib/market-board-types";

const LABELS: Record<string, string> = {
  KR: "한국 수출",
  US: "미국의 한국산 수입",
  HU: "헝가리의 한국산 수입",
  PL: "폴란드의 한국산 수입",
};

function compact(value: number, currency: string): string {
  return new Intl.NumberFormat("ko-KR", {
    notation: "compact",
    style: "currency",
    currency,
    maximumFractionDigits: 1,
  }).format(value);
}

function line(values: number[], maximum: number, width: number, height: number): string {
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  return values
    .map((value, index) => `${index * step},${height - (value / maximum) * height}`)
    .join(" ");
}

export default function MarketTrendChart({ series }: { series: MarketTimeSeries[] }) {
  const available = series.filter((item) => item.points.length > 0);
  if (available.length === 0) {
    return <p className="text-sm text-muted">월별 시계열은 다음 자동 갱신부터 누적됩니다.</p>;
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {available.map((item) => {
        const current = item.points.map((point) => point.value);
        const previous = item.points.map((point) => point.previous_value ?? 0);
        const maximum = Math.max(...current, ...previous, 1);
        const last = item.points.at(-1)!;
        return (
          <article key={`${item.country_code}-${item.measure}`} className="rounded-lg border border-card-border bg-background p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold">{LABELS[item.country_code] ?? item.country_code}</h3>
                <p className="mt-1 text-[13px] text-muted">월간 금액 · {item.currency} · {item.classification}</p>
              </div>
              <div className="text-right">
                <p className="text-sm font-semibold tabular-nums">{compact(last.value, item.currency)}</p>
                <p className="text-[13px] text-muted">{last.period}</p>
              </div>
            </div>
            <svg className="mt-4 h-36 w-full overflow-visible" viewBox="0 0 420 120" role="img" aria-label={`${LABELS[item.country_code] ?? item.country_code} 월별 추세`}>
              <line x1="0" y1="120" x2="420" y2="120" stroke="currentColor" className="text-card-border" />
              <polyline points={line(previous, maximum, 420, 110)} fill="none" stroke="currentColor" strokeWidth="2" strokeDasharray="5 5" className="text-muted" />
              <polyline points={line(current, maximum, 420, 110)} fill="none" stroke="currentColor" strokeWidth="3" className="text-foreground" />
            </svg>
            <div className="mt-2 flex items-center justify-between gap-2 text-[13px] text-muted">
              <span>{item.points[0].period}</span>
              <span>실선 당해년 · 점선 전년 동월</span>
              <span>{last.period}</span>
            </div>
          </article>
        );
      })}
    </div>
  );
}
