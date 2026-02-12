export type HealthStatus = "OK" | "WARN" | "CRITICAL";

export type HealthSnapshot = {
  status: HealthStatus;
  // optional fields (useful for richer alerts)
  actions?: string[];
  issues?: string[];
  kpis?: Record<string, unknown>;
};

export type AlertEvent = {
  name: string;            // e.g. "LLM_HEALTH_CRITICAL"
  severity: "info" | "warn" | "critical";
  message: string;
  timestamp: number;
  context?: Record<string, unknown>;
};

export interface Notifier {
  notify(event: AlertEvent): Promise<void> | void;
}
