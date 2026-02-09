import { FeatureSpec } from "@llmqa/core";
import { LLMAdapter } from "./LLMAdapter.js";
export declare class MockLLMAdapter implements LLMAdapter {
    private promptEngine;
    private model;
    generateTestCases(spec: FeatureSpec): Promise<{
        id: string;
        title: string;
        steps: string[];
        expected: string;
        tags: string[];
        risk: "low" | "medium" | "high";
        createdFromFeatureId: string;
    }[]>;
}
//# sourceMappingURL=MockLLMAdapter.d.ts.map