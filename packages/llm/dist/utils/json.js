/**
 * Utility per il parsing sicuro di JSON con gestione degli errori
 */
export function safeJsonParse(jsonString) {
    try {
        return JSON.parse(jsonString);
    }
    catch (error) {
        throw new Error(`Invalid JSON: ${error instanceof Error ? error.message : String(error)}`);
    }
}
//# sourceMappingURL=json.js.map