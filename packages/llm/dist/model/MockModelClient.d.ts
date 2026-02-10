import { ModelClient } from "./ModelClient.js";
/**
 * Mock deterministic provider:
 * returns structured JSON for testCases.
 * Later this will be replaced by real providers (OpenAI/Anthropic/etc).
 */
export declare class MockModelClient implements ModelClient {
    complete(_prompt: string, opts?: {
        signal?: AbortSignal;
    }): Promise<string>;
}
//# sourceMappingURL=MockModelClient.d.ts.map