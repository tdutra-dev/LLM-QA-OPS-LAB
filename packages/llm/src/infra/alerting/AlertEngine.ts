import type { AlertEvent, HealthSnapshot, Notifier } from "./types";

type AlertEngineOptions = {
  cooldownMs?: number; // avoid spamming
};

export class AlertEngine {
  private lastFiredAtByName = new Map<string, number>();
  private cooldownMs: number;

  constructor(private notifier: Notifier, opts: AlertEngineOptions = {}) {
    this.cooldownMs = opts.cooldownMs ?? 60_000; // 1 min default
  }

  /**
   * MVP rule:
   * - if health is CRITICAL -> fire alert (with cooldown)
   */
  async evaluateHealth(health: HealthSnapshot): Promise<void> {
    if (health.status !== "CRITICAL") return;

    const event: AlertEvent = {
      name: "LLM_HEALTH_CRITICAL",
      severity: "critical",
      message: "LLM pipeline health is CRITICAL (retries/timeouts/failures above threshold).",
      timestamp: Date.now(),
      context: {
        actions: health.actions ?? [],
        issues: health.issues ?? [],
        kpis: health.kpis ?? {},
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
