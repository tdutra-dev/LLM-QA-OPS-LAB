import { z } from "zod";
export const FeatureSpecSchema = z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    description: z.string().min(1),
    acceptanceCriteria: z.array(z.string().min(1)).min(1),
    tags: z.array(z.string().min(1)).default([]),
});
export const TestCaseSchema = z.object({
    id: z.string().min(1),
    title: z.string().min(1),
    steps: z.array(z.string().min(1)).min(1),
    expected: z.string().min(1),
    tags: z.array(z.string().min(1)).default([]),
    risk: z.enum(["low", "medium", "high"]).default("medium"),
    createdFromFeatureId: z.string().min(1),
});
//# sourceMappingURL=types.js.map