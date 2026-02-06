export type PromptVersion = "v1";

export type PromptId = {
  name: "generate_testcases";
  version: PromptVersion;
};

export function promptPath(id: PromptId): string {
  return new URL(`../../prompts/${id.version}/${id.name}.prompt.md`, import.meta.url).pathname;
}
