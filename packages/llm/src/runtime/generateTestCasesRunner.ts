import type { FeatureSpec } from "@llmqa/core";
import type { LLMAdapter } from "../LLMAdapter.js";
import { generateTestCases } from "../usecases/generateTestCases.js";
import { metrics } from "../infra/metrics/index.js";

import type { FailureMode, ServiceName } from "@llmqa/sim/types";

export function createGenerateTestCasesRunner(
  llm: LLMAdapter,
  spec: FeatureSpec
) {
  return async function runPipeline({
    requestId,
    service,
    injected,
  }: {
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
  }) {
    const start = Date.now();

    try {
      // 👉 QUI puoi iniettare comportamento nel mock adapter
      // Se usi MockModelClient, puoi passare injected flags lì.
      
      metrics.reset();

      await generateTestCases(llm, spec);

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
}

function classifyError(err: any): FailureMode {
  if (!err) return "none";

  if (err.name === "AbortError") return "timeout";
  if (err.message?.includes("JSON")) return "invalid_json";
  if (err.message?.includes("schema")) return "schema_mismatch";

  return "network";
}
