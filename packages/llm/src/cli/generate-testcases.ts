import { readFile } from "node:fs/promises";
import { FeatureSpecSchema } from "@llmqa/core";
import { MockLLMAdapter } from "../MockLLMAdapter.js";
import { generateTestCases } from "../usecases/generateTestCases.js";

async function main() {
  const raw = await readFile(
    new URL("../../../core/fixtures/featureSpec.checkout.json", import.meta.url),
    "utf-8"
  );

  const spec = FeatureSpecSchema.parse(JSON.parse(raw));
  const llm = new MockLLMAdapter();

  const testCases = await generateTestCases(llm, spec);

  console.log(JSON.stringify({ specId: spec.id, testCases }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
