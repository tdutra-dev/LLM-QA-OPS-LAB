import { evaluateIncident } from "./evaluationClient";
import { EvaluationRequest } from "@llmqa/contracts";

async function main(): Promise<void> {
  const request: EvaluationRequest = {
    incident: {
      id: "inc_001",
      timestamp: "2026-03-10T09:12:00Z",
      workflow: "test-generation",
      stage: "output-validation",
      incidentType: "schema_error",
      category: "invalid_json",
      severity: "high",
      source: "validation-layer",
      message: "LLM output failed schema validation: invalid JSON structure",
      context: {
        provider: "mock-llm",
        model: "mock-v1",
        expectedSchema: "TestCaseSchema",
        retryCount: 1,
      },
    },
    requestMeta: {
      sourceSystem: "llm-qa-ops-core",
      requestedBy: "evaluation-demo",
      correlationId: "corr_001",
    },
  };

  const result = await evaluateIncident(request, {
    baseUrl: "http://127.0.0.1:8010",
    timeoutMs: 5000,
  });

  console.log("Evaluation result:");
  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error("Demo evaluation failed:");
  console.error(error);
  process.exit(1);
});