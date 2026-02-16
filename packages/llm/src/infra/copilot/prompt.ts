import type { CopilotInput } from "./types";

export type CopilotPrompt = {
  system: string;
  user: string;
};

export function buildCopilotPrompt(input: CopilotInput): CopilotPrompt {
  const system =
    "You are an Incident Copilot for backend + LLM systems. " +
    "Your job is to interpret telemetry (KPIs, issues, health) and propose next steps. " +
    "Be concise, practical, and avoid speculation. If unsure, say so. " +
    "Return ONLY valid JSON with keys: summary, probableCause, suggestedActions, confidence. " +
    "confidence must be a number between 0 and 1.";

  const user = JSON.stringify(
    {
      incident: {
        service: input.service,
        environment: input.environment,
        healthStatus: input.healthStatus,
        timestamp: new Date(input.timestamp).toISOString(),
      },
      kpis: input.kpis,
      issues: input.issues,
    },
    null,
    2
  );

  return { system, user };
}
