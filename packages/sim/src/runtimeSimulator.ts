// packages/sim/src/runtimeSimulator.ts

import type { SimulationProfile, ServiceName, FailureMode } from "./types.js";
import type { RuntimeEventBus } from "./eventBus.js";
import { mulberry32, pickOne, chance, jitter } from "./rng.js";

type PipelineResult = {
  ok: boolean;
  attempts: number;
  usedFallback: boolean;
  failureMode: FailureMode;
  latencyMs: number;
};

export type PipelineRunner = (args: {
  requestId: string;
  service: ServiceName;
  injected: {
    shouldFail: boolean;
    shouldTimeout: boolean;
    invalidJson: boolean;
    schemaMismatch: boolean;
    latencyMs: number;
    forceFallback: boolean;
  };
}) => Promise<PipelineResult>;

export type HealthEvaluator = (window: PipelineResult[]) => {
  health: "OK" | "DEGRADED" | "CRITICAL";
  kpis: Record<string, number>;
  reason?: string;
};

export type AlertAndCopilot = (input: {
  health: "DEGRADED" | "CRITICAL";
  reason: string;
  kpis: Record<string, number>;
}) => Promise<{ summary: string; confidence: number } | null>;

export class RuntimeSimulator {
  constructor(
    private deps: {
      bus: RuntimeEventBus;
      runPipeline: PipelineRunner;
      evaluateHealth: HealthEvaluator;
      alertAndCopilot: AlertAndCopilot;
    }
  ) {}

  async simulate(profile: SimulationProfile) {
    const rand = mulberry32(profile.seed);

    const resultsWindow: PipelineResult[] = [];
    const windowSize = Math.max(profile.evaluateEveryN, 10);

    // mutable probabilities (for degradation)
    let probs = { ...profile.probabilities };

    for (let i = 1; i <= profile.requests; i++) {
      if (profile.degradation?.enabled && i % profile.degradation.everyNRequests === 0) {
        probs = {
          ...probs,
          fail: clamp01(probs.fail + (profile.degradation.addFail ?? 0)),
          timeout: clamp01(probs.timeout + (profile.degradation.addTimeout ?? 0)),
          fallback: clamp01(probs.fallback + (profile.degradation.addFallback ?? 0)),
        };
      }

      const service = pickOne(rand, profile.services);
      const requestId = `req_${profile.seed}_${i}`;

      const latencyMs = jitter(rand, profile.latency.baseMs, profile.latency.jitterMs);

      const injected = {
        shouldFail: chance(rand, probs.fail),
        shouldTimeout: chance(rand, probs.timeout),
        invalidJson: chance(rand, probs.invalidJson),
        schemaMismatch: chance(rand, probs.schemaMismatch),
        latencyMs,
        forceFallback: chance(rand, probs.fallback),
      };

      this.deps.bus.emit({
        type: "request_started",
        requestId,
        service,
        timestamp: Date.now(),
      });

      const result = await this.deps.runPipeline({ requestId, service, injected });

      this.deps.bus.emit({
        type: "request_finished",
        requestId,
        service,
        timestamp: Date.now(),
        latencyMs: result.latencyMs,
        attempts: result.attempts,
        usedFallback: result.usedFallback,
        ok: result.ok,
        failureMode: result.failureMode,
      });

      resultsWindow.push(result);
      if (resultsWindow.length > windowSize) resultsWindow.shift();

      // Health evaluation cadence
      if (i % profile.evaluateEveryN === 0) {
        const evalRes = this.deps.evaluateHealth(resultsWindow);

        this.deps.bus.emit({
          type: "health_evaluated",
          timestamp: Date.now(),
          windowSize: resultsWindow.length,
          health: evalRes.health,
          kpis: evalRes.kpis,
        });

        if (evalRes.health !== "OK") {
          const reason = evalRes.reason ?? "Health degraded based on KPIs";

          this.deps.bus.emit({
            type: "alert_triggered",
            timestamp: Date.now(),
            health: evalRes.health,
            reason,
          });

          const copilot = await this.deps.alertAndCopilot({
            health: evalRes.health,
            reason,
            kpis: evalRes.kpis,
          });

          if (copilot) {
            this.deps.bus.emit({
              type: "copilot_generated",
              timestamp: Date.now(),
              summary: copilot.summary,
              confidence: copilot.confidence,
            });
          }
        }
      }
    }
  }
}

function clamp01(x: number) {
  if (x < 0) return 0;
  if (x > 1) return 1;
  return x;
}
