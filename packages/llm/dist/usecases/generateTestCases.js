/**
 * Use case: FeatureSpec -> TestCase[]
 * 1) riceve input validato (FeatureSpec dal core)
 * 2) chiama l'LLMAdapter (mock o reale)
 * 3) valida l'output con schema (Zod) per renderlo "safe"
 * 4) ritorna TestCase[] pronto per tooling/QA/automation
 */
import { z } from "zod";
import { TestCaseSchema } from "@llmqa/core";
import { metrics } from "../infra/metrics/index.js";
import { computeKPIs } from "../infra/metrics/kpi.js";
import { evaluateHealth } from "../infra/metrics/health.js";
import { AlertEngine, ConsoleNotifier } from "../infra/alerting/index.js";
const TestCaseArraySchema = z.array(TestCaseSchema);
export async function generateTestCases(llm, spec) {
    const raw = await llm.generateTestCases(spec);
    // Se il tuo adapter ritorna già oggetti -> validiamo direttamente.
    // Se ritorna stringa JSON -> parse e poi validiamo.
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    const snap = metrics.snapshot();
    const kpis = computeKPIs(snap);
    const formatRate = (num, den) => den === 0 ? "N/A" : ((num / den) * 100).toFixed(1) + "%";
    console.log("\n📊 metrics:", snap);
    console.log("\n📊 Reliability Report");
    console.log("---------------------");
    console.log("Retry rate:", (kpis.retryRate * 100).toFixed(1) + "%");
    console.log("Fallback rate:", (kpis.fallbackRate * 100).toFixed(1) + "%");
    console.log("Recovery success rate:", formatRate(snap.recoverySuccesses, snap.recoveryAttempts));
    console.log("Avg attempts per request:", kpis.avgAttemptsPerRequest.toFixed(2));
    const health = evaluateHealth(snap);
    console.log("\n🩺 Health:", health.status);
    // if (health.issues.length) {
    //   for (const issue of health.issues) {
    //     console.log("-", issue);
    //   }
    // } else {
    //   console.log("- all KPIs within thresholds");
    // }
    console.log("\n🛠 Suggested actions");
    const unique = [...new Set(health.actions)];
    if (unique.length) {
        for (const a of unique)
            console.log("-", a);
    }
    else {
        console.log("- no actions needed");
    }
    const alertEngine = new AlertEngine(new ConsoleNotifier(), { cooldownMs: 60_000 });
    await alertEngine.evaluateHealth({
        status: health.status,
        actions: health.actions,
        issues: health.issues //,
        //kpis: health.kpis, // only if your health object includes it; otherwise remove this
    });
    console.log("\n\n-----------------------------\n\n");
    return TestCaseArraySchema.parse(parsed);
}
//# sourceMappingURL=generateTestCases.js.map