import { LLMAdapter } from "./LLMAdapter";
import { FeatureSpec, TestCase } from "../../core/src";
export declare class MockLLMAdapter implements LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
//# sourceMappingURL=MockLLMAdapter.d.ts.map