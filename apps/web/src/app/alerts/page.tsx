import Link from "next/link";
import MainTabs from "@/components/MainTabs";
import {
  ALERT_CATEGORIES,
  ALERT_CATEGORY_LABELS,
  ALERT_SEVERITIES,
  ALERT_SEVERITY_LABELS,
  ALERT_STATUSES,
  ALERT_STATUS_LABELS,
  getAlertById,
  getAlerts,
  isAlertCategory,
  isAlertSeverity,
  isAlertStatus,
  type AlertFilters,
} from "@/lib/ops-preview-data";
import { OpsAlert } from "@/lib/ops-preview-types";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function readFilters(params: Record<string, string | string[] | undefined>) {
  const category = first(params.category);
  const severity = first(params.severity);
  const status = first(params.status);
  const date = first(params.date);

  const filters: AlertFilters = {};
  if (category && isAlertCategory(category)) filters.category = category;
  if (severity && isAlertSeverity(severity)) filters.severity = severity;
  if (status && isAlertStatus(status)) filters.status = status;
  if (date && /^\d{4}-\d{2}-\d{2}$/.test(date)) filters.date = date;
  return { filters, selectedId: first(params.id) };
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function severityClass(severity: OpsAlert["severity"]): string {
  const classes: Record<OpsAlert["severity"], string> = {
    critical: "border-red-300 bg-red-50 text-red-700",
    high: "border-amber-300 bg-amber-50 text-amber-800",
    medium: "border-blue-300 bg-blue-50 text-blue-700",
    low: "border-slate-300 bg-slate-50 text-slate-700",
  };
  return classes[severity];
}

function statusClass(status: OpsAlert["status"]): string {
  const classes: Record<OpsAlert["status"], string> = {
    open: "bg-red-100 text-red-700",
    monitoring: "bg-amber-100 text-amber-800",
    resolved: "bg-emerald-100 text-emerald-700",
    suppressed: "bg-slate-100 text-slate-700",
  };
  return classes[status];
}

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const { filters, selectedId } = readFilters(params);
  const alerts = getAlerts(filters);
  const selectedAlert =
    getAlertById(selectedId) ?? alerts[0] ?? getAlertById(undefined);

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-card-border pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Preview only
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">
            Alert review
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Local public-status fixtures for alert triage review. This screen has
            no production Supabase connection and exposes no delivery controls.
          </p>
        </div>
        <MainTabs active="alerts" />
      </header>

      <form className="grid gap-3 rounded-lg border border-card-border bg-card p-4 shadow-sm md:grid-cols-5">
        <FilterSelect name="category" label="Category" value={filters.category}>
          <option value="">All categories</option>
          {ALERT_CATEGORIES.map((category) => (
            <option key={category} value={category}>
              {ALERT_CATEGORY_LABELS[category]}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect name="severity" label="Severity" value={filters.severity}>
          <option value="">All severities</option>
          {ALERT_SEVERITIES.map((severity) => (
            <option key={severity} value={severity}>
              {ALERT_SEVERITY_LABELS[severity]}
            </option>
          ))}
        </FilterSelect>
        <FilterSelect name="status" label="Status" value={filters.status}>
          <option value="">All statuses</option>
          {ALERT_STATUSES.map((status) => (
            <option key={status} value={status}>
              {ALERT_STATUS_LABELS[status]}
            </option>
          ))}
        </FilterSelect>
        <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
          Date
          <input
            type="date"
            name="date"
            defaultValue={filters.date ?? ""}
            className="h-10 rounded-md border border-card-border bg-background px-3 text-sm text-foreground outline-none focus:border-accent"
          />
        </label>
        <div className="flex items-end gap-2">
          <button
            type="submit"
            className="h-10 rounded-md bg-foreground px-4 text-sm font-semibold text-background"
          >
            Apply
          </button>
          <Link
            href="/alerts"
            className="flex h-10 items-center rounded-md border border-card-border px-4 text-sm font-semibold text-muted hover:text-accent"
          >
            Reset
          </Link>
        </div>
      </form>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(420px,1.1fr)]">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              Matching events
            </h2>
            <span className="text-xs text-muted">{alerts.length} records</span>
          </div>
          {alerts.map((alert) => (
            <Link
              key={alert.id}
              href={{
                pathname: "/alerts",
                query: { ...filters, id: alert.id },
              }}
              className={`rounded-lg border bg-card p-4 shadow-sm transition-colors hover:border-accent ${
                selectedAlert?.id === alert.id
                  ? "border-accent"
                  : "border-card-border"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${severityClass(
                    alert.severity
                  )}`}
                >
                  {ALERT_SEVERITY_LABELS[alert.severity]}
                </span>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(
                    alert.status
                  )}`}
                >
                  {ALERT_STATUS_LABELS[alert.status]}
                </span>
                <span className="text-xs text-muted">
                  {ALERT_CATEGORY_LABELS[alert.category]}
                </span>
              </div>
              <h3 className="mt-3 text-base font-semibold text-foreground">
                {alert.title}
              </h3>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">
                {alert.publicSummary}
              </p>
              <p className="mt-3 text-xs text-muted">
                Updated {formatDateTime(alert.updatedAt)}
              </p>
            </Link>
          ))}
        </div>

        {selectedAlert ? (
          <article className="rounded-lg border border-card-border bg-card p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {selectedAlert.source}
                </p>
                <h2 className="mt-1 text-xl font-semibold text-foreground">
                  {selectedAlert.title}
                </h2>
                <p className="mt-2 text-sm text-muted">
                  {selectedAlert.region} · observed{" "}
                  {formatDateTime(selectedAlert.observedAt)}
                </p>
              </div>
              <span className="rounded-md border border-card-border px-2.5 py-1 text-xs font-semibold text-muted">
                {selectedAlert.privacyClass}
              </span>
            </div>
            <p className="mt-5 text-sm leading-6 text-foreground">
              {selectedAlert.publicSummary}
            </p>

            <h3 className="mt-7 text-sm font-semibold text-foreground">
              Event detail and update timeline
            </h3>
            <ol className="mt-4 space-y-4">
              {selectedAlert.timeline.map((event) => (
                <li
                  key={`${event.at}-${event.title}`}
                  className="border-l-2 border-card-border pl-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {event.title}
                    </span>
                    {event.status ? (
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${statusClass(
                          event.status
                        )}`}
                      >
                        {ALERT_STATUS_LABELS[event.status]}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-muted">
                    {formatDateTime(event.at)} · {event.actor}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {event.note}
                  </p>
                </li>
              ))}
            </ol>
          </article>
        ) : (
          <div className="rounded-lg border border-card-border bg-card p-5 text-sm text-muted">
            No alert fixture matches the selected filters.
          </div>
        )}
      </section>
    </main>
  );
}

function FilterSelect({
  name,
  label,
  value,
  children,
}: {
  name: string;
  label: string;
  value?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
      {label}
      <select
        name={name}
        defaultValue={value ?? ""}
        className="h-10 rounded-md border border-card-border bg-background px-3 text-sm text-foreground outline-none focus:border-accent"
      >
        {children}
      </select>
    </label>
  );
}
