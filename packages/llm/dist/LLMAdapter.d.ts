import type { FeatureSpec, TestCase } from "@llmqa/core";
export interface LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
//# sourceMappingURL=LLMAdapter.d.ts.map