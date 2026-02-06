export interface ModelClient {
  complete(prompt: string): Promise<string>;
}
