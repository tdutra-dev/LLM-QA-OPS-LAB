/**
 * Mock deterministico: riconosce il prompt e ritorna JSON coerente.
 * In futuro, questa classe sarà sostituita da OpenAI/Anthropic/etc.
 */
export class MockModelClient {
    async complete(_prompt) {
        return JSON.stringify({
            testCases: [
                {
                    id: "TC-001",
                    title: "Mostra messaggio di retry quando il provider va in timeout",
                    steps: ["Avvia checkout", "Simula timeout provider", "Osserva UI messaggio retry"],
                    expected: "Compare un messaggio che invita a riprovare il pagamento",
                    tags: ["checkout", "payment", "timeout"],
                    risk: "high",
                    createdFromFeatureId: "FEAT-001"
                },
                {
                    id: "TC-002",
                    title: "Non creare ordine se il pagamento non è confermato",
                    steps: ["Avvia checkout", "Simula timeout provider", "Verifica assenza ordine"],
                    expected: "Nessun ordine viene creato finché non arriva conferma pagamento",
                    tags: ["checkout", "payment", "order"],
                    risk: "high",
                    createdFromFeatureId: "FEAT-001"
                },
                {
                    id: "TC-003",
                    title: "Loggare correlationId per la richiesta di pagamento",
                    steps: ["Avvia checkout", "Esegui richiesta pagamento", "Controlla log applicativo"],
                    expected: "Nei log è presente correlationId legato alla richiesta di pagamento",
                    tags: ["observability", "logs", "correlationId"],
                    risk: "medium",
                    createdFromFeatureId: "FEAT-001"
                }
            ]
        }, null, 2);
    }
}
