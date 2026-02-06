import { z } from "zod";
/**
 * FeatureSpec = la "spec" di una funzionalità che vogliamo testare.
 * È il punto di partenza per generare test case (anche via LLM).
 */
export const FeatureSpecSchema = z.object({
    id: z.string().min(1), // es: "FEAT-001"
    title: z.string().min(1),
    description: z.string().min(1),
    acceptanceCriteria: z.array(z.string().min(1)).min(1),
    tags: z.array(z.string().min(1)).default([]),
});
