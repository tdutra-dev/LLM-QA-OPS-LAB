import { z } from "zod";
import { TestCaseSchema } from "@llmqa/core";
import { PromptEngine } from "./prompt/PromptEngine.js";
import { MockModelClient } from "./model/MockModelClient.js";
import { withFallback } from "./infra/resilience/withFallback.js";
import { withResilience } from "./infra/resilience/withResilience.js";
import { buildJsonRepairPrompt } from "./output/recovery.js";
import { safeJsonParse } from "./utils/json.js";
import { metrics } from "./infra/metrics/index.js";
const ModelOutputSchema = z.object({
    testCases: z.array(TestCaseSchema),
});
export class MockLLMAdapter {
    promptEngine = new PromptEngine();
    model = new MockModelClient();
    async generateTestCases(spec) {
        metrics.incRequests();
        const prompt = await this.promptEngine.buildPrompt({ name: "generate_testcases", version: "v1" }, spec);
        // 🟡 PRIMARY
        const primaryCall = () => withResilience(({ signal }) => this.model.complete(prompt, { signal }), {
            timeoutMs: 1000,
            maxAttempts: 3,
            baseDelayMs: 250,
            maxDelayMs: 4000,
            onAttempt: ({ attempt }) => console.log(`🟡 [primary] attempt=${attempt}`),
            onRetry: ({ attempt, delayMs, decision, err }) => console.log(`🔁 [primary] retry after attempt=${attempt} delay=${delayMs} reason=${decision.reason} err=${err?.name}`),
        });
        // 🟢 SECONDARY
        const secondaryCall = () => withResilience(({ signal }) => this.model.complete(prompt, { signal }), {
            timeoutMs: 1500,
            maxAttempts: 1,
            baseDelayMs: 250,
            maxDelayMs: 4000,
            onAttempt: ({ attempt }) => console.log(`🟢 [secondary] attempt=${attempt}`),
        });
        const raw = await withFallback(primaryCall, secondaryCall, {
            primaryName: "mock-primary",
            secondaryName: "mock-secondary",
            onFallback: ({ from, to, err }) => console.log(`🛟 [fallback] from=${from} to=${to} err=${err?.name}`),
        });
        let parsed;
        try {
            parsed = safeJsonParse(raw);
            const validated = ModelOutputSchema.parse(parsed);
            return validated.testCases;
        }
        catch (err) {
            console.log("⚠️ validation failed, attempting recovery...");
            metrics.incRecoveryAttempts();
            const repairPrompt = buildJsonRepairPrompt(raw);
            const repairedRaw = await this.model.complete(repairPrompt);
            parsed = safeJsonParse(repairedRaw);
            const validated = ModelOutputSchema.parse(parsed);
            metrics.incRecoverySuccesses(); // counts successful recoveries
            console.log("✅ recovery successful");
            return validated.testCases;
        }
    }
}
//# sourceMappingURL=MockLLMAdapter.js.map