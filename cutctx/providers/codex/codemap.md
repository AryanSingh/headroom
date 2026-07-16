# cutctx/providers/codex/

## Responsibility
Installs and launches OpenAI Codex integration with CutCtx model routing.

## Design
Installation updates Codex configuration idempotently; runtime builds proxy-aware environment/arguments.

## Flow
Setup registers endpoint/model settings; sessions send OpenAI-compatible requests through CutCtx.

## Integration
Used by provider CLI/global routing; integrates with Codex config, credentials, and OpenAI handlers.
