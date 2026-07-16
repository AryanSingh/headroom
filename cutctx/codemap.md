# cutctx/

## Responsibility
Implements the Python SDK and runtime for reducing LLM context cost while preserving useful information, with proxy, memory, provider, evaluation, and operational surfaces.

## Design
Public facades (`compress`, client/config/models) sit over composable transforms, tokenizers, relevance, caching, and storage. Provider/integration adapters isolate host APIs; the FastAPI proxy is the primary runtime assembly point. Nested packages own CLI, memory, orchestration, telemetry, security, installation, and enterprise-compatible extension seams.

## Flow
Content enters through the SDK, CLI, integrations, or proxy; configuration and token budgets select transforms/caches/routing; provider adapters send the resulting request; outcomes, savings, memory, and telemetry are recorded for later policy and reporting.

## Integration
The package exposes Python imports and command entrypoints, integrates with OpenAI/Anthropic/Gemini-compatible providers and agent tools, optionally loads the Rust core/ML runtimes, and is extended by `cutctx_ee` services.
