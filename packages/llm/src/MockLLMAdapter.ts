import { z } from "zod";
import { FeatureSpec, TestCaseSchema } from "@llmqa/core";
import { LLMAdapter } from "./LLMAdapter.js";
import { PromptEngine } from "./prompt/PromptEngine.js";
import { MockModelClient } from "./model/MockModelClient.js";
import { withFallback } from "./infra/resilience/withFallback.js";
import { withResilience } from "./infra/resilience/withResilience.js";
import { buildJsonRepairPrompt } from "./output/recovery.js";
import { safeJsonParse } from "./utils/json.js";

const ModelOutputSchema = z.object({
  testCases: z.array(TestCaseSchema),
});

export class MockLLMAdapter implements LLMAdapter {
  private promptEngine = new PromptEngine();
  private model = new MockModelClient();

  async generateTestCases(spec: FeatureSpec) {
    const prompt = await this.promptEngine.buildPrompt(
      { name: "generate_testcases", version: "v1" },
      spec
    );

    // 🟡 PRIMARY
    const primaryCall = () =>
      withResilience(
        ({ signal }) => this.model.complete(prompt, { signal }),
        {
          timeoutMs: 1000,
          maxAttempts: 3,
          baseDelayMs: 250,
          maxDelayMs: 4000,
          onAttempt: ({ attempt }) =>
            console.log(`🟡 [primary] attempt=${attempt}`),
          onRetry: ({ attempt, delayMs, decision, err }) =>
            console.log(
              `🔁 [primary] retry after attempt=${attempt} delay=${delayMs} reason=${decision.reason} err=${(err as any)?.name}`
            ),
        }
      );

    // 🟢 SECONDARY
    const secondaryCall = () =>
      withResilience(
        ({ signal }) => this.model.complete(prompt, { signal }),
        {
          timeoutMs: 1500,
          maxAttempts: 1,
          baseDelayMs: 250,
          maxDelayMs: 4000,
          onAttempt: ({ attempt }) =>
            console.log(`🟢 [secondary] attempt=${attempt}`),
        }
      );

    const raw = await withFallback(primaryCall, secondaryCall, {
      primaryName: "mock-primary",
      secondaryName: "mock-secondary",
      onFallback: ({ from, to, err }) =>
        console.log(
          `🛟 [fallback] from=${from} to=${to} err=${(err as any)?.name}`
        ),
    });

    let parsed;
    try {
      parsed = safeJsonParse(raw);
      const validated = ModelOutputSchema.parse(parsed);
      return validated.testCases;
    } catch (err) {
      console.log("⚠️ validation failed, attempting recovery...");

      const repairPrompt = buildJsonRepairPrompt(raw);

      const repairedRaw = await this.model.complete(repairPrompt);

      parsed = safeJsonParse(repairedRaw);
      const validated = ModelOutputSchema.parse(parsed);

      console.log("✅ recovery successful");
      return validated.testCases;
    }
  }
}
