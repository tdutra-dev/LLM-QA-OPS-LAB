import type { CopilotOutput } from "../copilot/types.js";

export type HealthStatus = "OK" | "WARN" | "CRITICAL";

export type HealthKpis = {
  retryRate?: number;
  fallbackRate?: number;
  avgAttempts?: number;
  recoveryFailRate?: number;
  [key: string]: unknown;
};

export type HealthSnapshot = {
  status: HealthStatus;
  actions?: string[];
  issues?: string[];
  kpis?: HealthKpis;
  copilot?: CopilotOutput;
};

export type AlertContext = {
  actions?: string[];
  issues?: string[];
  kpis?: HealthKpis;
  copilot?: CopilotOutput;
};

export type AlertEvent = {
  name: string;
  severity: "info" | "warn" | "critical";
  message: string;
  timestamp: number;
  context?: AlertContext;
};

export interface Notifier {
  notify(event: AlertEvent): Promise<void> | void;
}
