import { describe, it, expect } from "vitest";
import { IncidentCopilot } from "./IncidentCopilot.js";

describe("IncidentCopilot", () => {
  it("returns stub output when no llm is provided", async () => {
    const copilot = new IncidentCopilot(undefined);

    const out = await copilot.analyze({
      service: "svc",
      environment: "dev",
      healthStatus: "CRITICAL",
      kpis: { retryRate: 0.2, fallbackRate: 0.1, avgAttempts: 1.2 },
      issues: ["timeout spike"],
      timestamp: Date.now(),
    });

    expect(out.summary).toBeTruthy();
    expect(out.suggestedActions.length).toBeGreaterThan(0);
    expect(out.confidence).toBeGreaterThanOrEqual(0);
  });
});
