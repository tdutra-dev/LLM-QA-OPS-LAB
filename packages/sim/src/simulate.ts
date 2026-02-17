// packages/sim/src/simulate.ts

import { RuntimeEventBus } from "./eventBus.js";
import { consoleSink } from "./consoleSink.js";
import { RuntimeSimulator } from "./runtimeSimulator.js";
import type { SimulationProfile, FailureMode } from "./types.js";

// Import LLM dependencies
import { MockLLMAdapter } from "@llmqa/llm";
import { generateTestCases } from "@llmqa/llm";
import { metrics } from "@llmqa/llm";
import type { FeatureSpec } from "@llmqa/core";
import type { PipelineRunner, HealthEvaluator, AlertAndCopilot } from "./runtimeSimulator.js";

// Mock feature spec for testing
const mockFeatureSpec: FeatureSpec = {
  id: "FEAT-001",
  title: "User Login",
  description: "Users should be able to authenticate with email and password",
  acceptanceCriteria: [
    "User enters valid email and password",
    "System validates credentials",
    "System creates session on success"
  ],
  tags: ["authentication", "login"]
};

// Create LLM adapter instance
const llm = new MockLLMAdapter();

// Pipeline runner that calls generateTestCases
const createTestCasesRunner = (
  llmAdapter: MockLLMAdapter,
  spec: FeatureSpec
): PipelineRunner => {
  return async ({ requestId, service, injected }) => {
    const start = Date.now();

    try {
      // Reset metrics for each run
      metrics.reset();

      // Configure the mock adapter with injected behaviors
      if (injected.shouldTimeout) {
        // Simulate timeout behavior in the adapter
      }
      if (injected.invalidJson) {
        // Mock adapter could return invalid JSON
      }
      if (injected.schemaMismatch) {
        // Mock adapter could return schema mismatch
      }

      // Execute generateTestCases - this is what gets run 100 times!
      const testCases = await generateTestCases(llmAdapter, spec);

      const snap = metrics.snapshot();
      const attempts = snap.attempts ?? 1;
      const usedFallback = (snap.fallbacks ?? 0) > 0;

      return {
        ok: true,
        attempts,
        usedFallback,
        failureMode: "none" as FailureMode,
        latencyMs: Date.now() - start,
      };
    } catch (err: any) {
      const snap = metrics.snapshot();
      const attempts = snap.attempts ?? 1;
      const usedFallback = (snap.fallbacks ?? 0) > 0;

      return {
        ok: false,
        attempts,
        usedFallback,
        failureMode: classifyError(err),
        latencyMs: Date.now() - start,
      };
    }
  };
};

function classifyError(err: any): FailureMode {
  if (!err) return "none";
  if (err.name === "AbortError") return "timeout";
  if (err.message?.includes("JSON")) return "invalid_json";
  if (err.message?.includes("schema")) return "schema_mismatch";
  return "network";
}

const evaluateHealth: HealthEvaluator = (window) => {
  const total = window.length;
  const failed = window.filter(r => !r.ok).length;
  const errorRate = failed / total;

  let health: "OK" | "DEGRADED" | "CRITICAL";
  if (errorRate <= 0.05) health = "OK";
  else if (errorRate <= 0.15) health = "DEGRADED";
  else health = "CRITICAL";

  return {
    health,
    kpis: {
      errorRate,
      avgLatency: window.reduce((sum, r) => sum + r.latencyMs, 0) / total,
      fallbackRate: window.filter(r => r.usedFallback).length / total,
    },
    reason: `Error rate: ${(errorRate * 100).toFixed(1)}%`,
  };
};

const alertAndCopilot: AlertAndCopilot = async ({ health, reason, kpis }) => {
  return {
    summary: `${health}: ${reason}. Focus on retry/fallback sources. KPIs=${JSON.stringify(kpis)}`,
    confidence: 0.72,
  };
};

async function main() {
  const bus = new RuntimeEventBus();
  bus.on(consoleSink);

  // Create the pipeline runner that will execute generateTestCases
  const runPipeline = createTestCasesRunner(llm, mockFeatureSpec);

  const sim = new RuntimeSimulator({ 
    bus, 
    runPipeline, 
    evaluateHealth, 
    alertAndCopilot 
  });

  // Configuration for 100 test executions
  const profile: SimulationProfile = {
    seed: 1337,
    requests: 100, // This will run generateTestCases() 100 times!
    services: ["llm", "serviceA", "serviceB"],
    latency: { baseMs: 250, jitterMs: 200 },
    probabilities: {
      fail: 0.08,
      timeout: 0.03,
      fallback: 0.12,
      invalidJson: 0.02,
      schemaMismatch: 0.02,
    },
    degradation: {
      enabled: true,
      everyNRequests: 20,
      addFail: 0.03,
      addTimeout: 0.02,
      addFallback: 0.02,
    },
    evaluateEveryN: 10,
  };

  console.log(`🚀 Starting simulation: ${profile.requests} generateTestCases() executions`);
  await sim.simulate(profile);
  console.log("✅ Simulation completed!");
}

main().catch(err => {
  console.error("❌ Simulation failed:", err);
  process.exit(1);
});