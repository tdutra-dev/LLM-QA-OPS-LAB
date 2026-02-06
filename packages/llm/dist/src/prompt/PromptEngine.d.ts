import { FeatureSpec } from "../../core/src/index";
import { PromptId } from "./PromptId";
export declare class PromptEngine {
    buildPrompt(id: PromptId, spec: FeatureSpec): Promise<string>;
}
