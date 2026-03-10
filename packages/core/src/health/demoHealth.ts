import { evaluateIncident } from "../evaluation/evaluationClient";
import { computeWorkflowHealth } from "./computeWorkflowHealth";
import { EvaluationRequest } from "@llmqa/contracts";

async function main(): Promise<void> {
  const request: EvaluationRequest = {
    incident: {
      id: "inc_002",
      timestamp: "2026-03-10T10:00:00Z",
      workflow: "test-generation",
      stage: "output-validation",
      incidentType: "schema_error",
      category: "invalid_json",
      severity: "high",
      source: "validation-layer",
      message: "LLM output failed schema validation",
      context: {
        provider: "mock-llm",
        model: "mock-v1",
      },
    },
    requestMeta: {
      sourceSystem: "llm-qa-ops-core",
      requestedBy: "health-demo",
      correlationId: "corr_002",
    },
  };

  const evaluation = await evaluateIncident(request);

  console.log("\nEvaluation result:");
  console.log(JSON.stringify(evaluation, null, 2));

  const health = computeWorkflowHealth(request.incident.workflow, evaluation);

  console.log("\nWorkflow health:");
  console.log(JSON.stringify(health, null, 2));
}

main().catch((error) => {
  console.error("Health demo failed:");
  console.error(error);
  process.exit(1);
});