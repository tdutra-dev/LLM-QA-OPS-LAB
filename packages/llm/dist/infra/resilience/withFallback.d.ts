export type FallbackOptions = {
    shouldFallback?: (err: unknown) => boolean;
    onFallback?: (info: {
        from: string;
        to: string;
        err: unknown;
    }) => void;
};
export declare function withFallback<T>(primary: () => Promise<T>, secondary: () => Promise<T>, opts?: FallbackOptions & {
    primaryName?: string;
    secondaryName?: string;
}): Promise<T>;
//# sourceMappingURL=withFallback.d.ts.map