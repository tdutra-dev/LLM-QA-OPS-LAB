import { LLMAdapter } from "./LLMAdapter";
import { FeatureSpec, TestCase } from "../../core/src";

export class MockLLMAdapter implements LLMAdapter {
  async generateTestCases(spec: FeatureSpec): Promise<TestCase[]> {
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
