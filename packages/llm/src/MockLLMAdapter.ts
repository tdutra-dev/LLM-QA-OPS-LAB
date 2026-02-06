import { z } from "zod";
import { FeatureSpec, TestCaseSchema } from "@llmqa/core";
import { LLMAdapter } from "./LLMAdapter";
import { PromptEngine } from "./prompt/PromptEngine";
import { MockModelClient } from "./model/MockModelClient";

const ModelOutputSchema = z.object({
  testCases: z.array(TestCaseSchema)
});

export class MockLLMAdapter implements LLMAdapter {
  private promptEngine = new PromptEngine();
  private model = new MockModelClient();

  async generateTestCases(spec: FeatureSpec) {
    const prompt = await this.promptEngine.buildPrompt(
      { name: "generate_testcases", version: "v1" },
      spec
    );

    const raw = await this.model.complete(prompt);
    const parsed = JSON.parse(raw);
    const validated = ModelOutputSchema.parse(parsed);

    // (Per ora il mock restituisce FEAT-001 hardcoded: lo sistemiamo subito dopo)
    return validated.testCases;
  }
}
