export type HealthStatus = "OK" | "WARN" | "CRITICAL";
export type HealthSnapshot = {
    status: HealthStatus;
    actions?: string[];
    issues?: string[];
    kpis?: Record<string, unknown>;
};
export type AlertEvent = {
    name: string;
    severity: "info" | "warn" | "critical";
    message: string;
    timestamp: number;
    context?: Record<string, unknown>;
};
export interface Notifier {
    notify(event: AlertEvent): Promise<void> | void;
}
//# sourceMappingURL=types.d.ts.map