import { z } from "zod";
/**
 * FeatureSpec = la "spec" di una funzionalità che vogliamo testare.
 * È il punto di partenza per generare test case (anche via LLM).
 */
export declare const FeatureSpecSchema: z.ZodObject<{
    id: z.ZodString;
    title: z.ZodString;
    description: z.ZodString;
    acceptanceCriteria: z.ZodArray<z.ZodString>;
    tags: z.ZodDefault<z.ZodArray<z.ZodString>>;
}, z.core.$strip>;
export type FeatureSpec = z.infer<typeof FeatureSpecSchema>;
