import { z } from "zod";
export declare const RiskSchema: z.ZodEnum<{
    low: "low";
    medium: "medium";
    high: "high";
}>;
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
export type Risk = z.infer<typeof RiskSchema>;
export type TestCase = z.infer<typeof TestCaseSchema>;
//# sourceMappingURL=testCase.d.ts.map