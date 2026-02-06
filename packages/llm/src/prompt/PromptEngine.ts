import { readFile } from "node:fs/promises";
import { FeatureSpec } from "@llmqa/core";
import { PromptId, promptPath } from "./PromptId";
import { renderTemplate } from "./render";

export class PromptEngine {
  async buildPrompt(id: PromptId, spec: FeatureSpec): Promise<string> {
    const template = await readFile(promptPath(id), "utf-8");
    const specJson = JSON.stringify(spec, null, 2);
    return renderTemplate(template, {
      FEATURE_SPEC_JSON: specJson
    });
  }
}
