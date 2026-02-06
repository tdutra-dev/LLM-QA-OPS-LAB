import { z } from "zod";
export declare const FeatureSpecSchema: z.ZodObject<{
    id: z.ZodString;
    title: z.ZodString;
    description: z.ZodString;
    acceptanceCriteria: z.ZodArray<z.ZodString>;
    tags: z.ZodDefault<z.ZodArray<z.ZodString>>;
}, z.core.$strip>;
export type FeatureSpec = z.infer<typeof FeatureSpecSchema>;
export declare const TestCaseSchema: z.ZodObject<{
    id: z.ZodString;
    title: z.ZodString;
    steps: z.ZodArray<z.ZodString>;
    expected: z.ZodString;
    tags: z.ZodDefault<z.ZodArray<z.ZodString>>;
    risk: z.ZodDefault<z.ZodEnum<{
        low: "low";
        medium: "medium";
        high: "high";
    }>>;
    createdFromFeatureId: z.ZodString;
}, z.core.$strip>;
export type TestCase = z.infer<typeof TestCaseSchema>;
//# sourceMappingURL=types.d.ts.map