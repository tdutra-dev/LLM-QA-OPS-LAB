/**
 * Use case: FeatureSpec -> TestCase[]
 * 1) riceve input validato (FeatureSpec dal core)
 * 2) chiama l'LLMAdapter (mock o reale)
 * 3) valida l'output con schema (Zod) per renderlo "safe"
 * 4) ritorna TestCase[] pronto per tooling/QA/automation
 */
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