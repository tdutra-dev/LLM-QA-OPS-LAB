export function promptPath(id) {
    return new URL(`../../prompts/${id.version}/${id.name}.prompt.md`, import.meta.url).pathname;
}
