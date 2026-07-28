import MainTabs from "@/components/MainTabs";
import { getOperationsSnapshot } from "@/lib/ops-preview-data";
import { OpsRuntime, PublicStatusCheck } from "@/lib/ops-preview-types";

function formatDateTime(value: string | null): string {
  if (!value) return "Not run in preview";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
}

function statusClass(status: OpsRuntime["status"]): string {
  const classes: Record<OpsRuntime["status"], string> = {
    inactive: "bg-slate-100 text-slate-700",
    "shadow-ready": "bg-emerald-100 text-emerald-700",
    "preview-only": "bg-blue-100 text-blue-700",
    fresh: "bg-emerald-100 text-emerald-700",
    stale: "bg-amber-100 text-amber-800",
    failing: "bg-red-100 text-red-700",
  };
  return classes[status];
}

function checkClass(status: PublicStatusCheck["status"]): string {
  const classes: Record<PublicStatusCheck["status"], string> = {
    pass: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-amber-200 bg-amber-50 text-amber-800",
    fail: "border-red-200 bg-red-50 text-red-700",
    unknown: "border-slate-200 bg-slate-50 text-slate-700",
  };
  return classes[status];
}

export default function OperationsPage() {
  const snapshot = getOperationsSnapshot();
  const services = snapshot.runtimes.filter((runtime) => runtime.kind === "service");
  const jobs = snapshot.runtimes.filter((runtime) => runtime.kind === "job");

  return (
    <main className="mx-auto flex w-full max-w-7xl flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 border-b border-card-border pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">
            Read-only preview
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-foreground">
            Operations status
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted">
            Declared services and jobs from local public-status fixtures. The
            screen intentionally omits start, stop, retry, and control actions.
          </p>
        </div>
        <MainTabs active="operations" />
      </header>

      <section className="grid gap-3 rounded-lg border border-card-border bg-card p-4 shadow-sm md:grid-cols-3">
        <StatusMetric label="Schema" value={snapshot.schemaVersion} />
        <StatusMetric label="Generated" value={formatDateTime(snapshot.generatedAt)} />
        <StatusMetric label="Privacy class" value={snapshot.privacyClass} />
      </section>

      <RuntimeSection title="Declared services" runtimes={services} />
      <RuntimeSection title="Declared jobs" runtimes={jobs} />
    </main>
  );
}

function StatusMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
      </p>
      <p className="mt-1 break-words text-sm font-semibold text-foreground">
        {value}
      </p>
    </div>
  );
}

function RuntimeSection({
  title,
  runtimes,
}: {
  title: string;
  runtimes: OpsRuntime[];
}) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold text-foreground">{title}</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        {runtimes.map((runtime) => (
          <article
            key={runtime.id}
            className="rounded-lg border border-card-border bg-card p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                  {runtime.owner} · {runtime.kind}
                </p>
                <h3 className="mt-1 text-lg font-semibold text-foreground">
                  {runtime.name}
                </h3>
              </div>
              <span
                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass(
                  runtime.status
                )}`}
              >
                {runtime.status}
              </span>
            </div>

            <p className="mt-4 text-sm leading-6 text-muted">
              {runtime.publicSummary}
            </p>

            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2">
              <InfoItem label="Declared in" value={runtime.declaredIn} />
              <InfoItem label="Schedule" value={runtime.schedule} />
              <InfoItem label="Last run" value={formatDateTime(runtime.lastRunAt)} />
              <InfoItem
                label="Next expected"
                value={formatDateTime(runtime.nextExpectedAt)}
              />
              <InfoItem
                label="Freshness"
                value={
                  runtime.freshnessMinutes === null
                    ? "Placeholder"
                    : `${runtime.freshnessMinutes} minutes`
                }
              />
              <InfoItem label="Failure state" value={runtime.failureState} />
            </dl>

            <div className="mt-5 rounded-md border border-card-border bg-background p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                Control policy
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">
                {runtime.controlPolicy}
              </p>
            </div>

            <div className="mt-5 space-y-2">
              {runtime.checks.map((check) => (
                <div
                  key={`${runtime.id}-${check.name}`}
                  className={`rounded-md border p-3 ${checkClass(check.status)}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold">{check.name}</p>
                    <span className="text-xs font-semibold uppercase">
                      {check.status}
                    </span>
                  </div>
                  <p className="mt-1 text-xs">
                    {formatDateTime(check.observedAt)}
                  </p>
                  <p className="mt-2 text-sm leading-6">{check.summary}</p>
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
      </dt>
      <dd className="mt-1 break-words font-medium text-foreground">{value}</dd>
    </div>
  );
}
