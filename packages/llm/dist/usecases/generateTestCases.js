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
    return TestCaseArraySchema.parse(parsed);
}
//# sourceMappingURL=generateTestCases.js.map