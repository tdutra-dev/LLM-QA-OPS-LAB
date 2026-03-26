import { AlertEngine } from "../infra/alerting/AlertEngine.js";
import { OpenAILlmClient } from "../infra/copilot/OpenAILlmClient.js";
import type { AlertEvent } from "../infra/alerting/types.js";

// Use a real OpenAI client if OPENAI_API_KEY is set in the environment,
// otherwise fall back to the deterministic stub (useful for CI/offline dev).
const llmClient = process.env.OPENAI_API_KEY
  ? new OpenAILlmClient() // reads OPENAI_API_KEY from env automatically
  : undefined;

if (llmClient) {
  console.log("🤖 IncidentCopilot: using OpenAI GPT-4o-mini");
} else {
  console.log("⚠️  OPENAI_API_KEY not set — falling back to stub mode");
  console.log("   Set it in .env or export OPENAI_API_KEY=sk-... to enable AI reasoning.");
}

const notifier = {
  notify(event: AlertEvent) {
    console.log("🚨 ALERT FIRED:", event.name);
  },
};

const engine = new AlertEngine(notifier, { llmClient });

await engine.evaluateHealth({
  status: "CRITICAL",
  issues: ["timeout spike", "fallback rate above 20%"],
  kpis: {
    retryRate: 0.5,
    fallbackRate: 0.2,
    avgAttempts: 2.4,
  },
});
