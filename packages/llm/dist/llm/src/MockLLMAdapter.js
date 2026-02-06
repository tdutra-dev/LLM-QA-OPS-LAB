export class MockLLMAdapter {
    async generateTestCases(spec) {
        return [
            {
                id: "TC-001",
                title: `Retry payment on timeout (${spec.title})`,
                steps: [
                    "Avvia checkout",
                    "Simula timeout del provider di pagamento",
                    "Verifica messaggio di retry"
                ],
                expected: "L'utente vede un messaggio di retry e nessun ordine viene creato",
                tags: ["payment", "timeout", "retry"],
                risk: "high",
                createdFromFeatureId: spec.id
            }
        ];
    }
}
//# sourceMappingURL=MockLLMAdapter.js.map