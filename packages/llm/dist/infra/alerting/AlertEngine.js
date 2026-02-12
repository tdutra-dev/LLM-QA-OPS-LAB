export class AlertEngine {
    notifier;
    lastFiredAtByName = new Map();
    cooldownMs;
    constructor(notifier, opts = {}) {
        this.notifier = notifier;
        this.cooldownMs = opts.cooldownMs ?? 60_000; // 1 min default
    }
    /**
     * MVP rule:
     * - if health is CRITICAL -> fire alert (with cooldown)
     */
    async evaluateHealth(health) {
        if (health.status !== "CRITICAL")
            return;
        const event = {
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
    async fireWithCooldown(event) {
        const last = this.lastFiredAtByName.get(event.name) ?? 0;
        const now = event.timestamp;
        if (now - last < this.cooldownMs)
            return;
        this.lastFiredAtByName.set(event.name, now);
        await this.notifier.notify(event);
    }
}
//# sourceMappingURL=AlertEngine.js.map