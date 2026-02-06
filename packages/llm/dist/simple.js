"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.TestCaseSchema = exports.FeatureSpecSchema = exports.MockLLMAdapter = void 0;
const zod_1 = require("zod");
// Types
const FeatureSpecSchema = zod_1.z.object({
    id: zod_1.z.string().min(1),
    title: zod_1.z.string().min(1),
    description: zod_1.z.string().min(1),
    acceptanceCriteria: zod_1.z.array(zod_1.z.string().min(1)).min(1),
    tags: zod_1.z.array(zod_1.z.string().min(1)).default([]),
});
exports.FeatureSpecSchema = FeatureSpecSchema;
const TestCaseSchema = zod_1.z.object({
    id: zod_1.z.string().min(1),
    title: zod_1.z.string().min(1),
    steps: zod_1.z.array(zod_1.z.string().min(1)).min(1),
    expected: zod_1.z.string().min(1),
    tags: zod_1.z.array(zod_1.z.string().min(1)).default([]),
    risk: zod_1.z.enum(["low", "medium", "high"]).default("medium"),
    createdFromFeatureId: zod_1.z.string().min(1),
});
exports.TestCaseSchema = TestCaseSchema;
// Implementation
class MockLLMAdapter {
    async generateTestCases(spec) {
        return [
            {
                id: "TC-001",
                title: `Test per ${spec.title}`,
                steps: ["Step 1", "Step 2"],
                expected: "Expected result",
                tags: ["test"],
                risk: "medium",
                createdFromFeatureId: spec.id
            }
        ];
    }
}
exports.MockLLMAdapter = MockLLMAdapter;
//# sourceMappingURL=simple.js.map