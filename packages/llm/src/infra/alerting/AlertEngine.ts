import type { AlertEvent, HealthSnapshot, Notifier } from "./types.js";
import type { CopilotInput } from "../copilot/types.js";
import { IncidentCopilot, formatCopilotReport } from "../copilot/index.js";
import type { LlmClient } from "../copilot/IncidentCopilot.js";

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

type AlertEngineOptions = {
  cooldownMs?: number; // avoid spamming
  /**
   * Optional LLM client to power the IncidentCopilot.
   * If omitted, the copilot falls back to a deterministic stub.
   * Wire an OpenAILlmClient here to get real AI reasoning.
   */
  llmClient?: LlmClient;
};

export class AlertEngine {
  private lastFiredAtByName = new Map<string, number>();
  private cooldownMs: number;
  private llmClient?: LlmClient;

  constructor(private notifier: Notifier, opts: AlertEngineOptions = {}) {
    this.cooldownMs = opts.cooldownMs ?? 60_000;
    this.llmClient = opts.llmClient;
  }

  async evaluateHealth(health: HealthSnapshot): Promise<void> {
    if (health.status !== "CRITICAL") return;

    const copilot = new IncidentCopilot(this.llmClient);

    const kpis = health.kpis ?? {};

    const copilotInput = {
      service: "llm-pipeline",
      environment: "local",
      healthStatus: health.status,
      kpis: {
        retryRate: num(kpis.retryRate, 0),
        fallbackRate: num(kpis.fallbackRate, 0),
        avgAttempts: num(kpis.avgAttempts, 0),
      },
      issues: health.issues ?? [],
      timestamp: Date.now(),
    } satisfies CopilotInput;

    const copilotOutput = await copilot.analyze(copilotInput);
    console.log(formatCopilotReport(copilotInput, copilotOutput));

    const event: AlertEvent = {
      name: "LLM_HEALTH_CRITICAL",
      severity: "critical",
      message: "LLM pipeline health is CRITICAL (retries/timeouts/failures above threshold).",
      timestamp: Date.now(),
      context: {
        actions: health.actions ?? [],
        issues: health.issues ?? [],
        kpis: health.kpis ?? {},
        copilot: copilotOutput,
      },
    };

    await this.fireWithCooldown(event);
  }

  private async fireWithCooldown(event: AlertEvent): Promise<void> {
    const last = this.lastFiredAtByName.get(event.name) ?? 0;
    const now = event.timestamp;

    if (now - last < this.cooldownMs) return;

    this.lastFiredAtByName.set(event.name, now);
    await this.notifier.notify(event);
  }
}
