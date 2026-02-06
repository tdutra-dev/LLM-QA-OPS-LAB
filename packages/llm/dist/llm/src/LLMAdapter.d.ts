import { FeatureSpec, TestCase } from "../../core/src";
export interface LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
//# sourceMappingURL=LLMAdapter.d.ts.map