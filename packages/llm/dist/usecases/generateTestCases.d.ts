/**
 * Use case: FeatureSpec -> TestCase[]
 * 1) riceve input validato (FeatureSpec dal core)
 * 2) chiama l'LLMAdapter (mock o reale)
 * 3) valida l'output con schema (Zod) per renderlo "safe"
 * 4) ritorna TestCase[] pronto per tooling/QA/automation
 */
import { type FeatureSpec, type TestCase } from "@llmqa/core";
import type { LLMAdapter } from "../LLMAdapter.js";
export declare function generateTestCases(llm: LLMAdapter, spec: FeatureSpec): Promise<TestCase[]>;
//# sourceMappingURL=generateTestCases.d.ts.map