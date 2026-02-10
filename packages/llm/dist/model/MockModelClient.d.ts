import { ModelClient } from "./ModelClient.js";
export declare class MockModelClient implements ModelClient {
    complete(_prompt: string, opts?: {
        signal?: AbortSignal;
    }): Promise<string>;
}
//# sourceMappingURL=MockModelClient.d.ts.map