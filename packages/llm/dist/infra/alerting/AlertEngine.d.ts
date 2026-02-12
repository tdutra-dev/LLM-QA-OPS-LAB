import type { HealthSnapshot, Notifier } from "./types";
type AlertEngineOptions = {
    cooldownMs?: number;
};
export declare class AlertEngine {
    private notifier;
    private lastFiredAtByName;
    private cooldownMs;
    constructor(notifier: Notifier, opts?: AlertEngineOptions);
    /**
     * MVP rule:
     * - if health is CRITICAL -> fire alert (with cooldown)
     */
    evaluateHealth(health: HealthSnapshot): Promise<void>;
    private fireWithCooldown;
}
export {};
//# sourceMappingURL=AlertEngine.d.ts.map