export type AlertCategory =
  | "earthquake"
  | "weather"
  | "space-weather"
  | "tsunami"
  | "system";

export type AlertSeverity = "critical" | "high" | "medium" | "low";

export type AlertStatus = "open" | "monitoring" | "resolved" | "suppressed";

export interface AlertTimelineEvent {
  at: string;
  actor: string;
  title: string;
  note: string;
  status?: AlertStatus;
}

export interface OpsAlert {
  id: string;
  category: AlertCategory;
  severity: AlertSeverity;
  status: AlertStatus;
  title: string;
  source: string;
  region: string;
  observedAt: string;
  updatedAt: string;
  publicSummary: string;
  privacyClass: "public-status";
  timeline: AlertTimelineEvent[];
}

export type RuntimeKind = "service" | "job";

export type RuntimeStatus =
  | "inactive"
  | "shadow-ready"
  | "preview-only"
  | "fresh"
  | "stale"
  | "failing";

export interface PublicStatusCheck {
  name: string;
  status: "pass" | "warn" | "fail" | "unknown";
  observedAt: string;
  summary: string;
}

export interface OpsRuntime {
  id: string;
  kind: RuntimeKind;
  name: string;
  owner: string;
  declaredIn: string;
  schedule: string;
  lastRunAt: string | null;
  nextExpectedAt: string | null;
  freshnessMinutes: number | null;
  status: RuntimeStatus;
  failureState: "none" | "placeholder" | "stale" | "failed";
  publicSummary: string;
  controlPolicy: "read-only-preview";
  checks: PublicStatusCheck[];
}

export interface OperationsSnapshot {
  schemaVersion: "ops-public-status/v0.proposal";
  generatedAt: string;
  privacyClass: "public-status-only";
  runtimes: OpsRuntime[];
}
