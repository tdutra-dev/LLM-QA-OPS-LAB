import { z } from "zod";

/**
 * High-level incident families detected in AI/LLM workflows.
 */
export const IncidentTypeValues = [
  "technical_error",
  "schema_error",
  "semantic_error",
  "degradation",
] as const;

export const IncidentTypeSchema = z.enum(IncidentTypeValues);
export type IncidentType = z.infer<typeof IncidentTypeSchema>;

/**
 * Severity level used for prioritization and alerting.
 */
export const SeverityValues = ["low", "medium", "high", "critical"] as const;

export const SeveritySchema = z.enum(SeverityValues);
export type Severity = z.infer<typeof SeveritySchema>;

/**
 * Standard incident contract accepted by the LLM-QA-OPS core.
 *
 * This object is expected to be produced by external adapters /
 * normalization layers that transform client-specific logs and signals
 * into a stable, platform-wide format.
 */
export const StandardIncidentSchema = z.object({
  id: z.string().min(1, "Incident id is required"),
  timestamp: z.string().datetime("timestamp must be a valid ISO datetime"),
  workflow: z.string().min(1, "workflow is required"),
  stage: z.string().min(1, "stage is required"),

  incidentType: IncidentTypeSchema,
  category: z.string().min(1, "category is required"),
  severity: SeveritySchema,

  source: z.string().min(1, "source is required"),
  message: z.string().min(1, "message is required"),

  /**
   * Optional raw context coming from adapters / upstream systems.
   * Kept flexible on purpose to support different client environments.
   */
  context: z.record(z.string(), z.unknown()).optional(),
});

export type StandardIncident = z.infer<typeof StandardIncidentSchema>;

/**
 * Example fixture useful for tests, demos, and documentation.
 */
export const exampleIncident: StandardIncident = {
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
};