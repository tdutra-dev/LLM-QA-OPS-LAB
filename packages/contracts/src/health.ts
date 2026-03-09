import { z } from "zod";

/**
 * High-level health state of an AI workflow.
 */
export const HealthStatusValues = [
  "healthy",
  "degraded",
  "unstable",
  "critical",
] as const;

export const HealthStatusSchema = z.enum(HealthStatusValues);
export type HealthStatus = z.infer<typeof HealthStatusSchema>;

/**
 * Trend direction for system health evolution.
 */
export const HealthTrendValues = [
  "stable",
  "improving",
  "worsening",
] as const;

export const HealthTrendSchema = z.enum(HealthTrendValues);
export type HealthTrend = z.infer<typeof HealthTrendSchema>;

/**
 * Health snapshot of a workflow at a specific moment in time.
 *
 * This object aggregates evaluation signals and incidents
 * to represent the operational state of an AI workflow.
 */
export const WorkflowHealthSchema = z.object({
  workflow: z.string().min(1),

  status: HealthStatusSchema,

  /**
   * Overall score representing system health (0–100).
   */
  score: z.number().min(0).max(100),

  /**
   * Trend of the system health.
   */
  trend: HealthTrendSchema,

  /**
   * Number of recent incidents detected in the workflow.
   */
  recentIncidentCount: z.number().min(0),

  /**
   * Short human-readable explanation of the current health state.
   */
  summary: z.string().min(1),

  /**
   * Optional timestamp when this health snapshot was generated.
   */
  timestamp: z.string().datetime().optional(),
});

export type WorkflowHealth = z.infer<typeof WorkflowHealthSchema>;

/**
 * Example fixture useful for tests and demos.
 */
export const exampleWorkflowHealth: WorkflowHealth = {
  workflow: "test-generation",
  status: "degraded",
  score: 62,
  trend: "worsening",
  recentIncidentCount: 4,
  summary:
    "Multiple schema validation errors detected in the output-validation stage.",
  timestamp: "2026-03-10T10:30:00Z",
};