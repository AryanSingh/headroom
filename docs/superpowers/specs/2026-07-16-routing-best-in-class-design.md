# Best-in-Class Routing Safeguards Design

## Goal

Make optimization routing capability-aware, ensure invalid client requests never fan out to fallback deployments, and report routing savings using both input and output usage when available.

## Scope

The work applies to the optimization router and its OpenAI Chat, OpenAI Responses, Anthropic, and Gemini ingress paths. It also applies to canonical orchestration failure classification and the shared model-routing savings finalization path.

It does not change role/binding policy, transport proof, provider/account restrictions, contract lifecycle, fallback ordering, or request payload transformations.

## Design

### 1. Capability contracts before optimization routing

Each ingress adapter will derive a normalized, provider-neutral set of request requirements from the original request body before `prepare_model_routing` is called. The normalized vocabulary is deliberately small and stable:

- `tool_calling`
- `structured_outputs`
- `json_mode`
- `vision`
- `audio`
- `streaming`

The optimization router will receive this set as `required_capabilities`. A route will declare the capabilities its target is proven to support. The router applies a downgrade only when the target capability set contains every required capability. An absent declaration is not proof: non-empty request requirements therefore retain the requested model unless the chosen target explicitly declares the requirement.

This gate runs after the existing high-risk complexity and confidence gates but before cost calculation. A retained decision records `target_missing_capabilities` plus the sorted missing requirements in its existing trace and routing metadata. Existing no-feature text-only routing remains unchanged.

The initial preset declarations will only include capabilities that the project already deliberately supports for a target; they will not infer capability parity from model names. Custom JSON route configuration may set `target_capabilities` and `medium_target_capabilities`.

### 2. Provider-neutral ingress extraction

Adapters own only syntactic extraction:

- OpenAI Chat: tools/tool choice, response-format JSON/schema, message image/audio content, and streaming.
- OpenAI Responses: tools, text format JSON/schema, input image/audio items, and streaming.
- Anthropic: tools/tool choice, image/document/audio content, and streaming.
- Gemini: function declarations, response MIME/schema configuration, inline image/audio content, and streaming.

All extraction helpers return the shared vocabulary and do not mutate payloads. Unknown structured/multimodal forms conservatively add a capability requirement rather than being treated as plain text.

### 3. Invalid-request failure classification

Add an `invalid_request` terminal classification for deterministic provider/client errors: HTTP 400, 404, 405, 406, 408, 409 when it denotes validation rather than quota, 410, 413, 415, 422, and other non-auth/non-rate-limit 4xx responses. This classification is not included in default fallback triggers and is never put in the cooldown trigger set.

Known transient categories retain current behavior: authentication (401/403), rate limit (429), quota exhaustion (402 and provider-confirmed quota conflicts), timeouts, transport errors, and 5xx provider outages.

The terminal execution result retains the original provider error and the receipt records `invalid_request`; it must not invoke another model or account.

### 4. Output-aware savings accounting

Routes will carry optional input and output prices for source, low target, and medium target. Cost lookup will retrieve both price dimensions when LiteLLM provides them. `finalize_savings` will accept input and optional output token usage and calculate the sum of known input and output cost deltas.

When output usage or output pricing is unavailable, the router continues to report the input-derived savings but records an `input_only` estimate flag. Token-routing volume remains the number of input tokens shifted, preserving the existing metric semantics.

### 5. Verification

The implementation must follow test-first cycles. Regression tests will prove:

- a low-complexity request with a capability requirement retains the source model unless the chosen route explicitly proves that capability;
- target capability parity permits the same downgrade;
- every ingress adapter derives the expected normalized requirements without changing its payload;
- a 400/422 provider error is terminal and does not invoke a fallback, while 429 and 5xx still do;
- mixed input/output pricing produces the exact realized dollar delta; missing output data produces an explicitly marked input-only estimate;
- the existing routing-quality benchmark and orchestration suite remain green.

## Error handling and compatibility

All new behavior is fail-closed for optimization downgrades and backward-compatible for routing configuration: old custom routes have no declared target capabilities, so only feature-bearing requests are retained. Existing text-only requests continue through their current preset routes.

The trace schema adds optional fields only, leaving existing consumers compatible. No prompt or response content is added to telemetry.

## Success criteria

- No optimization downgrade occurs for an undeclared required capability.
- Deterministic invalid provider requests produce one provider attempt and no cooldown/fallback.
- Routing USD savings include output deltas whenever complete usage and pricing are available.
- All focused router/orchestration tests and the deterministic routing-quality benchmark pass.
