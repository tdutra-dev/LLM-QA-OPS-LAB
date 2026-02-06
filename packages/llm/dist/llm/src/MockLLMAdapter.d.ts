import { LLMAdapter } from "./LLMAdapter";
import { FeatureSpec, TestCase } from "../../core/src/index";
export declare class MockLLMAdapter implements LLMAdapter {
    generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}
