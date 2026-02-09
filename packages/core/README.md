## Architecture / Data Flow

This repo is a monorepo with two main packages:

- `@llmqa/core`: domain models + runtime schemas (Zod)
- `@llmqa/llm`: prompt engine + LLM adapter (mock today, real providers later)

### End-to-end flow (current)

1. Load a `FeatureSpec` fixture (`packages/core/fixtures/...`)
2. Validate input with `FeatureSpecSchema` (runtime safety)
3. Build a deterministic prompt from a versioned template (`packages/llm/prompts/v1/...`)
4. Call the model through an adapter (`LLMAdapter` -> `MockLLMAdapter`)
5. Parse + validate the output with `TestCaseSchema` (Zod)
6. Return `TestCase[]` and print via CLI

FeatureSpec (JSON fixture)
-> FeatureSpecSchema.parse
-> PromptEngine (versioned prompt template)
-> LLMAdapter (mock today)
-> JSON output
-> TestCaseSchema[] validation
-> TestCase[]

kotlin
Copia codice

### Why this design

LLM outputs are non-deterministic by nature. This project treats the LLM as a component that must be:
- versioned (prompts)
- validated (schemas)
- testable (mock adapters)
- replaceable (provider-agnostic interface)
