export function renderTemplate(template, vars) {
    let out = template;
    for (const [key, value] of Object.entries(vars)) {
        out = out.replaceAll(`{{${key}}}`, value);
    }
    return out;
}
//# sourceMappingURL=render.js.map