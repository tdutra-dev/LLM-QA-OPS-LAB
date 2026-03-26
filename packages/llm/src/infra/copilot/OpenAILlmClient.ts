import OpenAI from "openai";
import type { LlmClient } from "./IncidentCopilot.js";

/**
 * OpenAI implementation of LlmClient.
 *
 * Uses `response_format: json_object` to force the model to return
 * valid JSON — no markdown fences, no prose, just the object.
 *
 * API key is read from the OPENAI_API_KEY environment variable,
 * or passed explicitly in the constructor.
 *
 * Usage:
 *   const client = new OpenAILlmClient();          // reads OPENAI_API_KEY from env
 *   const client = new OpenAILlmClient(myKey);     // explicit key
 *   const client = new OpenAILlmClient(key, "gpt-4o"); // different model
 */
export class OpenAILlmClient implements LlmClient {
  private client: OpenAI;
  private model: string;

  constructor(apiKey?: string, model = "gpt-4o-mini") {
    this.client = new OpenAI({
      apiKey: apiKey ?? process.env.OPENAI_API_KEY,
    });
    this.model = model;
  }

  async completeJson(args: { system: string; user: string }): Promise<unknown> {
    const response = await this.client.chat.completions.create({
      model: this.model,
      // Forces the model to return a valid JSON object — never plain text
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: args.system },
        { role: "user", content: args.user },
      ],
      // Low temperature = more deterministic, consistent structured output
      temperature: 0.2,
    });

    const content = response.choices[0]?.message?.content ?? "{}";

    // Parse the JSON string returned by the model
    return JSON.parse(content) as unknown;
  }
}
