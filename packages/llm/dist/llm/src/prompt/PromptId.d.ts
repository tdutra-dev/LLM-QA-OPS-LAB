export type PromptVersion = "v1";
export type PromptId = {
    name: "generate_testcases";
    version: PromptVersion;
};
export declare function promptPath(id: PromptId): string;
