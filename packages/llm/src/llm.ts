import { FeatureSpec, TestCase } from "./types.js";

export interface LLMAdapter {
  generateTestCases(spec: FeatureSpec): Promise<TestCase[]>;
}

export class MockLLMAdapter implements LLMAdapter {
  async generateTestCases(spec: FeatureSpec): Promise<TestCase[]> {
    return [
      {
        id: "TC-001",
        title: `Test per ${spec.title}`,
        steps: ["Step 1", "Step 2"],
        expected: "Expected result",
        tags: ["test"],
        risk: "medium" as const,
        createdFromFeatureId: spec.id
      }
    ];
  }
}