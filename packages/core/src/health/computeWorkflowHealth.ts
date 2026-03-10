import {
  EvaluationResult,
  WorkflowHealth,
  HealthStatus,
  HealthTrend,
} from "@llmqa/contracts";

/**
 * Compute a high-level workflow health snapshot from an evaluation result.
 *
 * This is the first step toward runtime operational intelligence:
 * - evaluation describes the incident
 * - health describes the system state
 */
export function computeWorkflowHealth(
  workflow: string,
  evaluation: EvaluationResult,
): WorkflowHealth {
  const status = mapStatus(evaluation.status);

  return {
    workflow,
    status,
    score: evaluation.score,
    trend: "stable",
  };
}

function mapStatus(status: EvaluationResult["status"]): HealthStatus {
  switch (status) {
    case "ok":
      return "healthy";

    case "needs_attention":
      return "degraded";

    case "critical":
      return "critical";

    default:
      return "unstable";
  }
}