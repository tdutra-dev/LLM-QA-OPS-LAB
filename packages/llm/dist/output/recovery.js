export function buildJsonRepairPrompt(badOutput) {
    return `
The previous response was not valid JSON.

Return ONLY valid JSON.
Do not include explanations, markdown or extra text.

Invalid response:
${badOutput}
`;
}
//# sourceMappingURL=recovery.js.map