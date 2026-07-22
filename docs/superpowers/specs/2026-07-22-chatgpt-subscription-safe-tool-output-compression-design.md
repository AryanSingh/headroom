# ChatGPT Subscription Safe Tool-Output Compression

## Problem

CutCtx sends ChatGPT subscription traffic through the OpenAI Responses API over
WebSocket or HTTP fallback. Earlier request transformations interrupted active
Codex sessions and corrupted model-bound continuation state. Codex could not
resume those sessions after a reconnect or proxy restart.

The current safeguard treats later ChatGPT subscription WebSocket frames as
full passthrough. That safeguard protects session recovery, but it also blocks
compression of mutable tool outputs. Recent sessions sent 32 to 34
`response.create` frames with zero compressed frames even when the request
contained large tool-result text.

CutCtx needs a smaller mutation boundary. It must keep continuation state and
provider-owned request fields unchanged while reducing ordinary tool-output
strings that ChatGPT has not bound to opaque resume state.

## Goals

- Preserve the existing session-recovery behavior for encrypted, opaque,
  compacted, and resumed ChatGPT subscription requests.
- Compress eligible tool-output strings on ordinary ChatGPT subscription
  requests.
- Apply one policy across the first WebSocket frame, later WebSocket frames,
  and HTTP fallback.
- Attribute accepted reductions to CutCtx compression without counting rejected
  or shadow transformations.
- Fall back to the existing safe request whenever classification, compression,
  or validation fails.

## Non-Goals

- Compress user, system, assistant, instruction, reasoning, or encrypted text.
- Compact or remove ChatGPT-owned tools and schemas.
- Change a requested model for ChatGPT subscription traffic.
- Reorder, remove, merge, or create Responses input items.
- Change API-key OpenAI, OpenCode, or Anthropic compression behavior.
- Transform remote-compaction requests.

## Approaches Considered

### Blanket passthrough

Keep the current subscription policy. This retains the strongest compatibility
posture but leaves mutable tool outputs uncompressed.

### Allowlisted compression for non-opaque turns

Classify each subscription request before compression. Requests with resume or
opaque state use the existing passthrough path. Other requests may change only
approved tool-output strings. A structural validator rejects any wider change.

This design uses this approach.

### Compression inside opaque continuations

Allow tool-output changes beside encrypted continuation state. This could
increase savings, but CutCtx cannot prove that ChatGPT treats those fields as
independent from its model-bound continuation. This approach does not satisfy
the session-recovery requirement.

## Safety Classification

CutCtx will classify the sanitized inner Responses payload before applying a
subscription compression transform.

The classifier returns `passthrough` when the payload has any of these traits:

- `_is_remote_compaction_subscription_request(payload)` returns true.
- `_contains_opaque_responses_continuation(payload)` returns true.
- An input item has type `compaction`.
- The payload contains a non-empty `previous_response_id`.
- The classifier cannot understand the input container or item shape.

The classifier returns `tool_outputs_only` when none of those traits exists and
the input is a list that contains at least one recognized tool-output item with
a string `output` value.

All other payloads use `passthrough` with a reason such as `no_eligible_output`.
The classifier will not inspect or log encrypted text, tool-output text, user
content, or credentials.

## Mutation Boundary

The subscription transform starts from the payload that the existing ChatGPT
sanitizer produced. The sanitizer keeps its current responsibility for required
transport fields such as `store` and `stream`.

The transform may replace only an `output` string at an input-list index whose
item type belongs to `OPENAI_RESPONSES_OUTPUT_TYPES`. It will use the existing
Responses `CompressionUnit` router so size floors, content classification,
latency guards, and compressor selection stay consistent with API-key traffic.

The subscription transform will not run these existing structural transforms:

- tool-surface slimming;
- tool-schema compaction;
- positional-array conversion through `compress_tool_results`;
- latest-user-tail compression;
- message compression; or
- model routing.

The code should expose the subscription behavior as a focused helper instead
of weakening the general `_compress_openai_responses_payload` contract. The
first WebSocket frame, later WebSocket frames, and HTTP fallback will call that
helper after subscription sanitization and before the final context guard.

## Structural Validation

CutCtx will compare the original sanitized payload with the candidate output
before it sends the candidate upstream.

The validator will require all of these invariants:

- Both payloads have the same top-level keys.
- Both payloads contain the same number of input items in the same order.
- Each input item keeps the same keys and values, except for an approved string
  `output` field.
- Item type, item ID, call ID, status, role, name, arguments, encrypted content,
  and content blocks remain equal.
- Model, tools, instructions, `previous_response_id`, metadata, request options,
  and envelope fields remain equal.
- Each accepted output replacement remains a string and is smaller by the
  tokenizer used for attribution.

The validator discards the full candidate when one invariant fails. CutCtx then
forwards the original sanitized payload and records a bounded passthrough reason
without request content.

## Request Flow

### WebSocket first frame

1. Parse and sanitize the ChatGPT subscription frame with the current logic.
2. Classify the inner payload.
3. Run the subscription tool-output helper only for `tool_outputs_only`.
4. Validate the candidate against the sanitized original.
5. Rewrap and forward the accepted candidate, or forward the sanitized original.

This replaces the first frame's current general compression call, which can
compact provider-owned tool schemas.

### Later WebSocket frames

The relay will replace `allow_payload_mutation=False` with the same classifier,
helper, and validator used for the first frame. Opaque and resumed frames keep
the existing full-passthrough behavior.

### HTTP fallback

The HTTP Responses handler will use the same subscription policy after
sanitization. Remote-compaction requests keep their existing exact bypass.
API-key OpenAI requests keep the general Responses compressor.

## Error Handling

The proxy will preserve session availability under each failure mode:

- A classifier error selects passthrough.
- A compression timeout or exception selects passthrough unless the existing
  non-opaque context guard requires a refusal.
- A structural validation failure selects passthrough.
- An opaque continuation bypasses local refusal based on an approximate token
  count, matching the current continuation policy.
- A remote-compaction request retains its current unchanged route.

The proxy must not close a WebSocket because the optional subscription
compression helper failed.

## Telemetry and Attribution

Accepted transformations increment `ws_frames_compressed`, add their token
savings to `tokens_saved`, and include the existing router transform names.
Rejected candidates add no savings.

Passthrough telemetry will use bounded reasons:

- `subscription_opaque_continuation`
- `subscription_previous_response_resume`
- `subscription_remote_compaction`
- `subscription_no_eligible_output`
- `subscription_compression_failed`
- `subscription_invariant_failed`

Logs and metrics will contain counts, byte totals, elapsed time, and reason
codes. They will not contain request text, encrypted state, tool output, or
credentials.

## Verification Plan

Development will follow a red-green sequence.

### Unit tests

- A non-opaque subscription payload with a large `function_call_output` fails
  under the current full-passthrough policy, then passes with reduced output.
- The validator accepts a change to one approved output string.
- The validator rejects changes to tools, model, call ID, item order, encrypted
  content, metadata, and top-level keys.
- Encrypted continuation, compaction, remote-compaction, malformed input, and
  `previous_response_id` payloads select passthrough.
- A compressor exception returns the original sanitized payload.

### WebSocket tests

- The first subscription frame does not compact tools and may compress an
  eligible ordinary tool output.
- A later ordinary frame may compress an eligible tool output.
- A later encrypted continuation reaches the fake ChatGPT upstream unchanged,
  keeps its requested model, and does not close with code 1009.
- A reconnect frame with `previous_response_id` reaches upstream unchanged.

### HTTP tests

- Ordinary subscription tool output uses the same allowlisted transform.
- Encrypted and resumed payloads preserve their protected fields.
- Remote compaction remains unchanged.
- API-key Responses requests retain existing schema and content compression.

### Replay tests

Extend the agent replay fixtures with a WebSocket tool-output turn followed by
an opaque resume turn and a proxy restart. The strict fake upstream will check
field preservation and emit `response.completed` for each accepted request.

Keep the existing `codex-subscription-http-resume` scenario green. It proves
that a restart preserves model, input, tools, `store`, `stream`, and terminal
events.

### Test commands

Run the focused tests first:

```bash
pytest -q \
  tests/test_openai_responses_context_compaction.py \
  tests/test_openai_responses_compression_units.py \
  tests/test_openai_codex_ws_lifecycle.py \
  tests/test_openai_codex_routing.py
```

Run the replay tests next:

```bash
pytest -q tests/agent_e2e/test_replay_harness.py
```

Run the surrounding OpenAI handler and model-router suites before completion.

## Rollout

The implementation will remain in the Python proxy, which owns ChatGPT
subscription routing. The native proxy keeps its documented unsupported status
for subscription routing.

After the automated suite passes, restart the local proxy with the existing
model-routing preset. Verify health, run an ordinary tool-output turn, then run
an opaque continuation or resume turn. The ordinary turn must report accepted
compression. The resume turn must complete without a local WebSocket refusal,
model rewrite, or payload-integrity error.

If live verification shows an interruption, restore the full-passthrough call
site while retaining the new tests and diagnostics for the next investigation.
