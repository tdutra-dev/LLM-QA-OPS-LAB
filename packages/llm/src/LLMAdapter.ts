/**
 * LLMAdapter = "porta" verso un modello LLM (mock o reale).
 * Il resto del sistema NON deve sapere quale provider usiamo.
 * Contratto: dato un FeatureSpec, ritorna test cases (strutturati).
 * In futuro: sostituibile con OpenAI/Anthropic/Azure senza cambiare i use case.
 */

import type { FeatureSpec, TestCase } from "@llmqa/core";

export interface LLMAdapter {
  generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
