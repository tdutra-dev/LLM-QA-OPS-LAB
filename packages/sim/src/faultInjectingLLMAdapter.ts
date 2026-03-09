// packages/sim/src/faultInjectingLLMAdapter.ts
import type { FeatureSpec } from "@llmqa/core";
import { MockLLMAdapter, metrics } from "@llmqa/llm";

export type InjectedFault = {
  shouldFail?: boolean;
  shouldTimeout?: boolean;
  invalidJson?: boolean;
  schemaMismatch?: boolean;
  latencyMs?: number;
  timeoutMs?: number;
  forceFallback?: boolean;
};

export class FaultInjectingLLMAdapter extends MockLLMAdapter {
  private nextFault: InjectedFault | null = null;

  setFault(fault: InjectedFault) {
    console.log("🧨 setFault called:", fault);
    this.nextFault = fault;
  }

  override async generateTestCases(spec: FeatureSpec): Promise<any> {
    console.log("🧨 generateTestCases() fault:", this.nextFault);
    const f = this.nextFault;
    this.nextFault = null;

    console.log("🧨 faultInjectingLLMAdapter - metrics.incRequests");
    // ✅ Always count the request
    metrics.incRequests();

    if (f?.latencyMs && f.latencyMs > 0) {
      console.log(`🧨 faultInjectingLLMAdapter - injecting latency: ${f.latencyMs}ms`);
      await sleep(f.latencyMs);
    }

    if (f?.shouldTimeout) {
      await sleep(f.timeoutMs ?? 5_000);
      const e: any = new Error("AbortError");
      e.name = "AbortError";
      throw e;
    }

    if (f?.invalidJson) {
      return "{not-valid-json";
    }

    if (f?.schemaMismatch) {
      return [{ title: 123, steps: "wrong-type" }];
    }

    if (f?.shouldFail) {
      throw new Error("NetworkError: simulated upstream failure");
    }

    // 🔁 Important: call super but avoid double-counting requests
    return super.generateTestCases(spec);
  }
}

function sleep(ms: number) {
  return new Promise<void>((res) => setTimeout(res, ms));
}
