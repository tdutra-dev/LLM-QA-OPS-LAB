import { FeatureSpec, TestCase } from "../../core/src/index";
export interface LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
