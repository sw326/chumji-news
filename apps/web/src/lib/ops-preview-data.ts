import fixtures from "./ops-preview-fixtures.json";
import { supabase } from "./supabase";
import {
  AlertCategory,
  AlertSeverity,
  AlertStatus,
  OperationsSnapshot,
  OpsAlert,
} from "./ops-preview-types";

export const ALERT_CATEGORIES: AlertCategory[] = [
  "earthquake",
  "weather",
  "space-weather",
  "tsunami",
  "system",
];

export const ALERT_SEVERITIES: AlertSeverity[] = [
  "critical",
  "high",
  "medium",
  "low",
];

export const ALERT_STATUSES: AlertStatus[] = [
  "open",
  "monitoring",
  "resolved",
  "suppressed",
];

export const ALERT_CATEGORY_LABELS: Record<AlertCategory, string> = {
  earthquake: "지진",
  weather: "기상",
  "space-weather": "우주 기상",
  tsunami: "지진해일",
  system: "시스템",
};

export const ALERT_SEVERITY_LABELS: Record<AlertSeverity, string> = {
  critical: "긴급",
  high: "높음",
  medium: "보통",
  low: "낮음",
};

export const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  open: "발생",
  monitoring: "관찰 중",
  resolved: "해결",
  suppressed: "알림 제외",
};

export interface AlertFilters {
  category?: AlertCategory;
  severity?: AlertSeverity;
  status?: AlertStatus;
  date?: string;
}

const alerts = fixtures.alerts as OpsAlert[];
const operations = fixtures.operations as OperationsSnapshot;

async function liveSnapshot<T>(kind: "alerts" | "operations"): Promise<T | null> {
  if (!supabase) return null;
  const { data, error } = await supabase
    .from("ops_public_snapshots")
    .select("payload")
    .eq("kind", kind)
    .maybeSingle();
  if (error || !data) return null;
  return data.payload as T;
}

export async function getAlerts(filters: AlertFilters = {}): Promise<OpsAlert[]> {
  const liveAlerts = (await liveSnapshot<OpsAlert[]>("alerts")) ?? alerts;
  return liveAlerts
    .filter((alert) => {
      if (filters.category && alert.category !== filters.category) return false;
      if (filters.severity && alert.severity !== filters.severity) return false;
      if (filters.status && alert.status !== filters.status) return false;
      if (filters.date && alert.observedAt.slice(0, 10) !== filters.date) {
        return false;
      }
      return true;
    })
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function getAlertById(
  alertsToSearch: OpsAlert[],
  id: string | undefined
): OpsAlert | undefined {
  if (!id) return alertsToSearch[0];
  return alertsToSearch.find((alert) => alert.id === id);
}

export async function getOperationsSnapshot(): Promise<OperationsSnapshot> {
  return (await liveSnapshot<OperationsSnapshot>("operations")) ?? operations;
}

export function isAlertCategory(value: string): value is AlertCategory {
  return ALERT_CATEGORIES.includes(value as AlertCategory);
}

export function isAlertSeverity(value: string): value is AlertSeverity {
  return ALERT_SEVERITIES.includes(value as AlertSeverity);
}

export function isAlertStatus(value: string): value is AlertStatus {
  return ALERT_STATUSES.includes(value as AlertStatus);
}
