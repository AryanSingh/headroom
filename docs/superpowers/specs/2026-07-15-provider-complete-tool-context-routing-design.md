# Provider-Complete Tool Context Routing Design

## Goal

Prevent model-routing downgrades while a recent conversation window contains provider-native tool calls or tool results, regardless of whether the request uses Anthropic messages, OpenAI Chat Completions, or OpenAI Responses items.

## Problem

`classify_task_complexity` promises to keep tool context on the requested strong model, but its current check recognizes only `role: tool` and three nested content-block types. It misses OpenAI Responses top-level `function_call` items, Chat Completions `tool_calls`, nested `function_call` blocks, and several supported call-output types. A short follow-up after those items can therefore be classified `LOW` and routed to Mini.

## Architecture

Add a private provider-neutral predicate in `cutctx/proxy/model_router.py` that recursively inspects each message in the existing recent-context window. It will identify:

- `role: tool` messages;
- call-like item types already supported by the proxy, including `tool_use`, `tool_call`, `function_call`, `function`, and custom/local-shell/apply-patch call variants;
- result/output item types, including `tool_result` and any `*_call_output` representation;
- Chat Completions `tool_calls` and legacy `function_call` fields;
- equivalent shapes nested under `content` or other provider containers.

The classifier will use this predicate only for the bounded recent window. Old tool activity outside that window will continue to expire, preserving the existing stale-context recovery behavior.

## Safety policy

- Recent tool calls and results always produce `TaskComplexity.HIGH`.
- Unknown structured or multimodal current user content remains `HIGH`.
- The canonical Mini/Luna/strong route table and cost calculations do not change.
- No additional dependency or external classifier is introduced.
- No routing aggressiveness is added in this phase.

## Testing

Follow red-green-refactor:

1. Add focused failing unit cases for Responses `function_call`, Chat `tool_calls`, nested `function_call`, and supported call-output types.
2. Verify the cases fail because they return `LOW` before implementation.
3. Implement the minimal recursive predicate and route existing recent-context logic through it.
4. Verify focused tests and existing stale-tool-context behavior.
5. Add provider-shape cases to the versioned routing-quality corpus and verify the CI benchmark remains at zero unsafe Mini downgrades.
6. Run the full routing, OpenAI Codex routing, and Anthropic routing test sets.

## Observability

Existing `recent_tool_context` assessment signals remain unchanged. This preserves routing trace compatibility while expanding the representations that correctly produce the signal.

## Non-goals

- Changing preset targets or reasoning effort.
- Increasing Mini or Luna coverage.
- Training or promoting a calibrated scorer.
- Adding downstream task evaluation in this bounded safety phase.

## Follow-up

The next independent project should add downstream task execution to the comparison harness and generate a portable quality/savings evidence bundle. That work should not be coupled to this routing bug fix.
