import { z } from "zod";
declare const FeatureSpecSchema: any;
type FeatureSpec = z.infer<typeof FeatureSpecSchema>;
declare const TestCaseSchema: any;
type TestCase = z.infer<typeof TestCaseSchema>;
interface LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
declare class MockLLMAdapter implements LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
export { FeatureSpec, TestCase, LLMAdapter, MockLLMAdapter, FeatureSpecSchema, TestCaseSchema };
//# sourceMappingURL=simple.d.ts.map