// Test file per verificare la configurazione TypeScript
import { FeatureSpec, TestCase } from "./packages/core/src";

const spec: FeatureSpec = {
  id: "TEST-001",
  title: "Test spec",
  description: "Test description", 
  acceptanceCriteria: ["Criteria 1"],
  tags: []
};

console.log("Test OK:", spec);