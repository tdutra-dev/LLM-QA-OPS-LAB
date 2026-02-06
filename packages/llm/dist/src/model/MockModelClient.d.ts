import { ModelClient } from "./ModelClient";
/**
 * Mock deterministico: riconosce il prompt e ritorna JSON coerente.
 * In futuro, questa classe sarà sostituita da OpenAI/Anthropic/etc.
 */
export declare class MockModelClient implements ModelClient {
    complete(_prompt: string): Promise<string>;
}
