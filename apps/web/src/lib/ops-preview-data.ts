import fixtures from "./ops-preview-fixtures.json";
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
  earthquake: "Earthquake",
  weather: "Weather",
  "space-weather": "Space weather",
  tsunami: "Tsunami",
  system: "System",
};

export const ALERT_SEVERITY_LABELS: Record<AlertSeverity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const ALERT_STATUS_LABELS: Record<AlertStatus, string> = {
  open: "Open",
  monitoring: "Monitoring",
  resolved: "Resolved",
  suppressed: "Suppressed",
};

export interface AlertFilters {
  category?: AlertCategory;
  severity?: AlertSeverity;
  status?: AlertStatus;
  date?: string;
}

const alerts = fixtures.alerts as OpsAlert[];
const operations = fixtures.operations as OperationsSnapshot;

export function getAlerts(filters: AlertFilters = {}): OpsAlert[] {
  return alerts
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

export function getAlertById(id: string | undefined): OpsAlert | undefined {
  if (!id) return alerts[0];
  return alerts.find((alert) => alert.id === id);
}

export function getOperationsSnapshot(): OperationsSnapshot {
  return operations;
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
