# ChatGPT Emergency Context Budget Design

## Problem

Codex remote compaction can send a Responses payload that is larger than the
model context window. The current ChatGPT subscription fallback calls
`_truncate_body_for_chatgpt()` with a byte ceiling, but the subsequent guard is
token-based. In the observed failure, a 1,388,746-byte / 516,873-token request
was reduced to 384,617 tokens, still above the 242,400-token safety threshold,
and CutCtx returned HTTP 413.

The current truncator is not a guaranteed budget reducer. It trims common text
and image fields, drops old top-level input items, and caps instructions, but it
can retain large tool schemas, function-call arguments, encrypted/opaque
payloads, nested strings, and one irreducibly large final input item.

## Desired Behavior

Before forwarding ChatGPT subscription traffic after a context-guard failure,
CutCtx must produce a schema-valid request that satisfies both:

- the conservative 900 KiB serialized-body ceiling; and
- the model-specific token threshold returned by the Responses context guard.

The reducer must preserve the newest user intent where possible, keep
function-call and function-result structure valid, avoid mutating the caller's
original body, and return a clear 413 only when the minimal valid request still
cannot fit.

## Design

Extend `_truncate_body_for_chatgpt()` with an optional token-budget callback.
The helper will use a single `over_budget()` predicate that checks serialized
bytes and, when supplied, token pressure. Existing byte-only callers retain
their current interface and behavior.

Reduction occurs in deterministic, schema-aware stages:

1. Recursively shrink oversized text, output, arguments, encrypted content,
   image data URIs, and other nested string payloads inside input items.
2. Drop the oldest complete top-level interaction items while retaining the
   newest item and removing leading orphaned tool results.
3. Remove tool definitions when still over budget. Historical compaction does
   not need the full live tool surface, and schemas are often the largest fixed
   payload component.
4. Progressively reduce instructions rather than retaining a fixed 200 KiB
   floor.
5. Apply a final recursive string cap to non-routing payload fields if a single
   retained item remains oversized.

The HTTP context-guard path will pass a callback backed by
`_openai_responses_context_guard()`, then re-check the returned body exactly as
it does today. The WS-to-HTTP byte-only fallback will continue using the helper
without the callback.

## Safety Rules

- Preserve routing and protocol fields such as `model`, `stream`, and scalar
  request options.
- Do not replace an image with non-image text; retain the existing valid 1x1
  PNG placeholder.
- Do not leave a retained input sequence beginning with a tool-result item.
- Do not mutate the original request body.
- Do not bypass the final context guard. A request that cannot be made safe
  still fails closed with HTTP 413.

## Verification

Add regression tests that construct payloads dominated by tool schemas,
function-call arguments, encrypted content, instructions, and nested text. The
tests must first demonstrate that the current reducer remains over a synthetic
token budget, then verify the new reducer satisfies both token and byte limits,
preserves the newest user message, removes orphaned tool results, and leaves the
original body unchanged.

Run the focused context-compaction test module followed by the surrounding
OpenAI Responses test modules.
