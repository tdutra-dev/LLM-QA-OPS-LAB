import { z } from "zod";
import { TestCaseSchema } from "@llmqa/core";
import { PromptEngine } from "./prompt/PromptEngine";
import { MockModelClient } from "./model/MockModelClient";
const ModelOutputSchema = z.object({
    testCases: z.array(TestCaseSchema)
});
export class MockLLMAdapter {
    promptEngine = new PromptEngine();
    model = new MockModelClient();
    async generateTestCases(spec) {
        const prompt = await this.promptEngine.buildPrompt({ name: "generate_testcases", version: "v1" }, spec);
        const raw = await this.model.complete(prompt);
        const parsed = JSON.parse(raw);
        const validated = ModelOutputSchema.parse(parsed);
        // (Per ora il mock restituisce FEAT-001 hardcoded: lo sistemiamo subito dopo)
        return validated.testCases;
    }
}
//# sourceMappingURL=MockLLMAdapter.js.map