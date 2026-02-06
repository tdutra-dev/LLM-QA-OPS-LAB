export class MockLLMAdapter {
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
//# sourceMappingURL=llm.js.map