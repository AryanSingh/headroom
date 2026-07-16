# cutctx/backends/

## Responsibility
Defines pluggable LLM backend adapters used by compression and evaluation code.

## Design
`LLMBackend` is the provider-neutral contract; AnyLLM and LiteLLM implementations are interchangeable Strategy adapters.

## Flow
Callers submit prompts/messages through the common interface and receive normalized completion data while provider invocation stays inside the adapter.

## Integration
Consumed by compression and evaluation paths; integrates with optional AnyLLM/LiteLLM SDKs and environment credentials.
