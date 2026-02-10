import { ModelClient } from "./ModelClient.js";

function sleep(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const id = setTimeout(resolve, ms);

    if (!signal) return;

    if (signal.aborted) {
      clearTimeout(id);
      return reject(signal.reason ?? new Error("Aborted"));
    }

    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(id);
        reject(signal.reason ?? new Error("Aborted"));
      },
      { once: true }
    );
  });
}

let calls = 0;

/**
 * MOCK modes (via env):
 * - MOCK_FAIL_FIRST=1            → only retry (1st call is slow)
 * - MOCK_FAIL_FIRST=3            → force fallback if primary has maxAttempts=3
 * - MOCK_DELAY_MS=2000           → delay duration (must be > timeoutMs to trigger timeout)
 * - MOCK_BROKEN_JSON_FIRST=1     → return invalid JSON once (to test recovery loop)
 */
const FAIL_FIRST = Number(process.env.MOCK_FAIL_FIRST ?? "1"); // default: 1
const DELAY_MS = Number(process.env.MOCK_DELAY_MS ?? "2000"); // default: 2000

const BROKEN_JSON_FIRST = process.env.MOCK_BROKEN_JSON_FIRST === "1";
let brokenServed = false;

/**
 * Mock deterministic provider:
 * returns structured JSON for testCases.
 * Later this will be replaced by real providers (OpenAI/Anthropic/etc).
 */
export class MockModelClient implements ModelClient {
  async complete(_prompt: string, opts?: { signal?: AbortSignal }): Promise<string> {
    calls++;

    // 1) Simulate slow provider for the first FAIL_FIRST calls (to trigger timeout/retry)
    if (calls <= FAIL_FIRST) {
      console.log(`🔥 MOCK: simulo lentezza ${DELAY_MS}ms (call ${calls}/${FAIL_FIRST})`);
      await sleep(DELAY_MS, opts?.signal);
    }

    // 2) Return invalid JSON once to test the output recovery loop
    if (BROKEN_JSON_FIRST && !brokenServed) {
      brokenServed = true;
      console.log("🧪 MOCK: returning invalid JSON (to test recovery)");
      return `Sure! Here is your JSON:\n{ "testCases": [ }`; // intentionally broken
    }

    // 3) Normal valid response
    return JSON.stringify(
      {
        testCases: [
          {
            id: "TC-001",
            title: "Mostra messaggio di retry quando il provider va in timeout",
            steps: ["Avvia checkout", "Simula timeout provider", "Osserva UI messaggio retry"],
            expected: "Compare un messaggio che invita a riprovare il pagamento",
            tags: ["checkout", "payment", "timeout"],
            risk: "high",
            createdFromFeatureId: "FEAT-001",
          },
          {
            id: "TC-002",
            title: "Non creare ordine se il pagamento non è confermato",
            steps: ["Avvia checkout", "Simula timeout provider", "Verifica assenza ordine"],
            expected: "Nessun ordine viene creato finché non arriva conferma pagamento",
            tags: ["checkout", "payment", "order"],
            risk: "high",
            createdFromFeatureId: "FEAT-001",
          },
          {
            id: "TC-003",
            title: "Loggare correlationId per la richiesta di pagamento",
            steps: ["Avvia checkout", "Esegui richiesta pagamento", "Controlla log applicativo"],
            expected: "Nei log è presente correlationId legato alla richiesta di pagamento",
            tags: ["observability", "logs", "correlationId"],
            risk: "medium",
            createdFromFeatureId: "FEAT-001",
          },
        ],
      },
      null,
      2
    );
  }
}
