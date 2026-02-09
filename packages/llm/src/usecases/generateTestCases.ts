/**
 * Use case: FeatureSpec -> TestCase[]
 * 1) riceve input validato (FeatureSpec dal core)
 * 2) chiama l'LLMAdapter (mock o reale)
 * 3) valida l'output con schema (Zod) per renderlo "safe"
 * 4) ritorna TestCase[] pronto per tooling/QA/automation
 */


import { z } from "zod";
import { TestCaseSchema, type FeatureSpec, type TestCase } from "@llmqa/core";
import type { LLMAdapter } from "../LLMAdapter.js";

const TestCaseArraySchema = z.array(TestCaseSchema);

export async function generateTestCases(
  llm: LLMAdapter,
  spec: FeatureSpec
): Promise<TestCase[]> {
  const raw = await llm.generateTestCases(spec);

  // Se il tuo adapter ritorna già oggetti -> validiamo direttamente.
  // Se ritorna stringa JSON -> parse e poi validiamo.
  const parsed =
    typeof raw === "string" ? JSON.parse(raw) : raw;

  return TestCaseArraySchema.parse(parsed);
}
