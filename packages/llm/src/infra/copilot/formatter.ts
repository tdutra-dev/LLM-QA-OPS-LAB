import type { CopilotInput, CopilotOutput } from "./types.js";

export function formatCopilotReport(input: CopilotInput, output: CopilotOutput): string {
  const lines: string[] = [];

  lines.push("========================================");
  lines.push("🤖 INCIDENT COPILOT");
  lines.push("========================================");
  lines.push(`Service:       ${input.service}`);
  lines.push(`Environment:   ${input.environment}`);
  lines.push(`Health:        ${input.healthStatus}`);
  lines.push(`Timestamp:     ${new Date(input.timestamp).toISOString()}`);
  lines.push("");
  lines.push(`Summary:       ${output.summary}`);
  lines.push(`Cause:         ${output.probableCause}`);
  lines.push(`Confidence:    ${(output.confidence * 100).toFixed(0)}%`);
  lines.push("");
  lines.push("Suggested actions:");
  output.suggestedActions.forEach((a, i) => lines.push(`  ${i + 1}. ${a}`));
  lines.push("");
  lines.push("Signals:");
  lines.push(`  retryRate:    ${(input.kpis.retryRate * 100).toFixed(1)}%`);
  lines.push(`  fallbackRate: ${(input.kpis.fallbackRate * 100).toFixed(1)}%`);
  lines.push(`  avgAttempts:  ${input.kpis.avgAttempts.toFixed(2)}`);
  if (input.issues?.length) {
    lines.push("Issues:");
    input.issues.forEach((iss) => lines.push(`  - ${iss}`));
  }
  lines.push("========================================");

  return lines.join("\n");
}
