# cutctx/proxy/handlers/

## Responsibility
Implements provider-facing request handlers for Anthropic, Gemini, OpenAI, batch, and shared streaming.

## Design
Provider handlers are mixins/strategies over the central proxy, each owning request/response schema translation while sharing streaming and batch utilities. The OpenAI child package further separates Chat/Responses behavior.

## Flow
A FastAPI route dispatches to the provider handler, which normalizes input, runs proxy decisions/transforms, forwards upstream, and reconstructs provider-native streaming or JSON output.

## Integration
Composed into `CutctxProxy`; integrates with providers, intelligence pipeline, caches/memory, metrics, and the child OpenAI handler package.
