// packages/sim/src/consoleSink.ts
import type { RuntimeEvent } from "./events";
import type { EventHandler } from "./eventBus";

export const consoleSink: EventHandler = (e: RuntimeEvent) => {
  if (e.type === "request_finished") {
    console.log(
      `[${e.service}] ${e.requestId} ok=${e.ok} attempts=${e.attempts} fallback=${e.usedFallback} latency=${e.latencyMs} mode=${e.failureMode}`
    );
  }
  if (e.type === "health_evaluated") {
    console.log(`HEALTH=${e.health} kpis=`, e.kpis);
  }
  if (e.type === "alert_triggered") {
    console.log(`🚨 ALERT ${e.health}: ${e.reason}`);
  }
  if (e.type === "copilot_generated") {
    console.log(`🤖 COPILOT (${e.confidence}): ${e.summary}`);
  }
};
