# crates/cutctx-proxy/src/compression/

## Responsibility
Bridges HTTP provider payloads to core live-zone compression while enforcing model limits, auth-mode rules, cache safety, and fail-open forwarding.

## Design
Provider adapters handle Anthropic, OpenAI Chat, and OpenAI Responses schema differences. `provider_native` selects native/provider behavior; `model_limits` computes usable budgets. Live-zone modules isolate exactly which message blocks may change and return typed manifests/outcomes.

## Flow
Handler parses JSON and requested model -> determine provider, auth mode, and context budget -> call matching core live-zone transform with optional CCR store -> accept only validated beneficial output -> return serialized body plus manifest, or preserve original bytes on exclusion/failure.

## Integration
- Invoked by proxy, Bedrock, Vertex, and endpoint handlers.
- Depends on `cutctx-core::transforms::live_zone`, policy/config, CCR state, and observability.
