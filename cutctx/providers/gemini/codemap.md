# cutctx/providers/gemini/

## Responsibility
Installs and launches Gemini CLI integration with CutCtx.

## Design
Install/runtime adapters own Gemini paths, environment variables, and invocation.

## Flow
Setup writes managed endpoint settings; wrapped execution sends Gemini requests through CutCtx.

## Integration
Uses provider registry and Gemini proxy handler; interacts with local credentials/config.
