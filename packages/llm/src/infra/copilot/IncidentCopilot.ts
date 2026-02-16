import { buildCopilotPrompt } from "./prompt.js";
import type { CopilotInput, CopilotOutput } from "./types.js";
import { z } from "zod";

export interface LlmClient {
  // Minimal interface: you can adapt to your existing provider wrapper
  completeJson(args: { system: string; user: string }): Promise<unknown>;
}

const CopilotOutputSchema = z.object({
  summary: z.string().min(1),
  probableCause: z.string().min(1),
  suggestedActions: z.array(z.string().min(1)).min(1),
  confidence: z.number().min(0).max(1),
});

export class IncidentCopilot {
  constructor(private llm?: LlmClient) {}

  async analyze(input: CopilotInput): Promise<CopilotOutput> {
    // ✅ Stub fallback (if no LLM client wired yet)
    if (!this.llm) return this.stub(input);

    const { system, user } = buildCopilotPrompt(input);
    const raw = await this.llm.completeJson({ system, user });

    // ✅ runtime validation (robust)
    return this.normalize(raw);
  }

  private stub(input: CopilotInput): CopilotOutput {
    const summary =
      `Health is ${input.healthStatus} for ${input.service} (${input.environment}). ` +
      `retryRate=${(input.kpis.retryRate * 100).toFixed(0)}%, ` +
      `fallbackRate=${(input.kpis.fallbackRate * 100).toFixed(0)}%, ` +
      `avgAttempts=${input.kpis.avgAttempts.toFixed(2)}.`;

    const probableCause = input.issues?.length
      ? `Most likely related to: ${input.issues[0]}`
      : "Likely transient upstream instability or timeout pressure; not enough signals to be sure.";

    const suggestedActions: string[] = [
      "Check provider/service status and recent latency trends",
      "Inspect recent timeouts/errors around the same timestamp",
      "Consider increasing timeout or enabling fallback for stability",
      "If recurring, add signature + clustering for this failure mode",
    ];

    const confidence = input.issues?.length ? 0.65 : 0.45;

    return { summary, probableCause, suggestedActions, confidence };
  }

  private normalize(raw: unknown): CopilotOutput {
    // Accept raw JSON object, or JSON string (some providers may return string)
    let obj: unknown = raw ?? {};

    if (typeof obj === "string") {
      try {
        obj = JSON.parse(obj);
      } catch {
        return {
          summary: "Copilot could not parse model output as JSON.",
          probableCause: "Model returned invalid JSON.",
          suggestedActions: [
            "Check model/provider response format",
            "Enable JSON-only mode / tool mode if available",
            "Log raw output for debugging",
          ],
          confidence: 0.2,
        };
      }
    }

    const parsed = CopilotOutputSchema.safeParse(obj);
    if (!parsed.success) {
      return {
        summary: "Copilot output failed validation.",
        probableCause: "Model returned JSON that does not match the expected schema.",
        suggestedActions: [
          "Inspect schema mismatch details in logs",
          "Tighten prompt instructions (JSON keys + types)",
          "Add repair step or fallback to deterministic heuristics",
        ],
        confidence: 0.25,
      };
    }

    return parsed.data;
  }
}
