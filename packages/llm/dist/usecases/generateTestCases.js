import { z } from "zod";
import { TestCaseSchema } from "@llmqa/core";
const TestCaseArraySchema = z.array(TestCaseSchema);
export async function generateTestCases(llm, spec) {
    const raw = await llm.generateTestCases(spec);
    // Se il tuo adapter ritorna già oggetti -> validiamo direttamente.
    // Se ritorna stringa JSON -> parse e poi validiamo.
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return TestCaseArraySchema.parse(parsed);
}
//# sourceMappingURL=generateTestCases.js.map