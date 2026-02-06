import { FeatureSpec, TestCase } from "./types";
export interface LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
export declare class MockLLMAdapter implements LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
//# sourceMappingURL=llm.d.ts.map