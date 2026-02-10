const defaultShouldFallback = (err) => {
    // tipico: timeout, 429, 5xx
    const name = err?.name;
    const status = err?.status ?? err?.response?.status;
    return name === "TimeoutError" || name === "AbortError" || status === 429 || (status >= 500 && status <= 599);
};
export async function withFallback(primary, secondary, opts = {}) {
    const { shouldFallback = defaultShouldFallback, onFallback, primaryName = "primary", secondaryName = "secondary", } = opts;
    try {
        return await primary();
    }
    catch (err) {
        if (!shouldFallback(err))
            throw err;
        onFallback?.({ from: primaryName, to: secondaryName, err });
        return await secondary();
    }
}
//# sourceMappingURL=withFallback.js.map