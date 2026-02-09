import { readFile } from "node:fs/promises";
import { promptPath } from "./PromptId.js";
import { renderTemplate } from "./render.js";
export class PromptEngine {
    async buildPrompt(id, spec) {
        const template = await readFile(promptPath(id), "utf-8");
        const specJson = JSON.stringify(spec, null, 2);
        return renderTemplate(template, {
            FEATURE_SPEC_JSON: specJson
        });
    }
}
//# sourceMappingURL=PromptEngine.js.map