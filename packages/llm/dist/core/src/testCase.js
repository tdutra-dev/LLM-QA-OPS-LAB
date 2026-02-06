import { z } from "zod";
export const RiskSchema = z.enum(["low", "medium", "high"]);
export const TestCaseSchema = z.object({
    id: z.string().min(1), // es: "TC-001"
    title: z.string().min(1),
    steps: z.array(z.string().min(1)).min(1),
    expected: z.string().min(1),
    tags: z.array(z.string().min(1)).default([]),
    risk: RiskSchema.default("medium"),
    createdFromFeatureId: z.string().min(1), // es: "FEAT-001"
});
