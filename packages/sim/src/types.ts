// packages/sim/src/types.ts

export type ServiceName = "llm" | "serviceA" | "serviceB" | "serviceC";

export type FailureMode =
  | "none"
  | "timeout"
  | "network"
  | "rate_limit"
  | "invalid_json"
  | "schema_mismatch";

export type SimulationProfile = {
  seed: number;

  requests: number;

  services: ServiceName[];

  // latency in ms (base + jitter)
  latency: {
    baseMs: number;
    jitterMs: number;
  };

  // probabilities are 0..1
  probabilities: {
    fail: number;        // primary call failure chance
    timeout: number;     // chance to exceed timeout
    fallback: number;    // chance fallback is used
    invalidJson: number; // mock model returns junk
    schemaMismatch: number;
  };

  // “degradation” lets us increase probabilities over time
  degradation?: {
    enabled: boolean;
    everyNRequests: number;
    addFail?: number;
    addTimeout?: number;
    addFallback?: number;
  };

  // health evaluation cadence
  evaluateEveryN: number;
};
