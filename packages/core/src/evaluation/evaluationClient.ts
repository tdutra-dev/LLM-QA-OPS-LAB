import {
  EvaluationRequest,
  EvaluationRequestSchema,
  EvaluationResult,
  EvaluationResultSchema,
} from "@llmqa/contracts";

export type EvaluationClientOptions = {
  baseUrl?: string;
  timeoutMs?: number;
};

const DEFAULT_BASE_URL = "http://127.0.0.1:8010";
const DEFAULT_TIMEOUT_MS = 5000;

export async function evaluateIncident(
  request: EvaluationRequest,
  options: EvaluationClientOptions = {},
): Promise<EvaluationResult> {
  const baseUrl = options.baseUrl ?? DEFAULT_BASE_URL;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  // Validate request before sending it
  const validatedRequest = EvaluationRequestSchema.parse(request);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${baseUrl}/evaluate`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(validatedRequest),
      signal: controller.signal,
    });

    if (!response.ok) {
      const errorText = await safeReadText(response);
      throw new Error(
        `Evaluation service request failed: ${response.status} ${response.statusText}${errorText ? ` - ${errorText}` : ""}`,
      );
    }

    const json = (await response.json()) as unknown;

    // Validate response coming back from Python
    return EvaluationResultSchema.parse(json);
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(
        `Evaluation service request timed out after ${timeoutMs}ms`,
      );
    }

    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

async function safeReadText(response: Response): Promise<string> {
  try {
    return await response.text();
  } catch {
    return "";
  }
}