// packages/sim/src/events.ts

import type { FailureMode, ServiceName } from "./types";

export type RuntimeEvent =
  | {
      type: "request_started";
      requestId: string;
      service: ServiceName;
      timestamp: number;
    }
  | {
      type: "request_finished";
      requestId: string;
      service: ServiceName;
      timestamp: number;
      latencyMs: number;
      attempts: number;
      usedFallback: boolean;
      ok: boolean;
      failureMode: FailureMode;
    }
  | {
      type: "health_evaluated";
      timestamp: number;
      windowSize: number;
      health: "OK" | "DEGRADED" | "CRITICAL";
      kpis: Record<string, number>;
    }
  | {
      type: "alert_triggered";
      timestamp: number;
      health: "DEGRADED" | "CRITICAL";
      reason: string;
    }
  | {
      type: "copilot_generated";
      timestamp: number;
      summary: string;
      confidence: number;
    };
