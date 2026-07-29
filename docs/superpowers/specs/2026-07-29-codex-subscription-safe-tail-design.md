# Codex Subscription Safe Mutable-Tail Design

## Goal

Enable direct compression for a ChatGPT/Codex subscription request only when
the proxy can prove that the request contains no opaque continuation state and
the only mutation is a current, string-valued tool-output tail. Preserve all
other subscription payloads byte-for-byte apart from the existing required
subscription sanitization.

## Problem

Codex subscription sessions retransmit stateful Responses payloads over a
WebSocket. A payload may carry remote compaction, a previous-response resume,
or encrypted/opaque continuation data. These structures must not be rewritten:
they are part of the provider's conversation state and their historical prefix
is also where provider prompt-cache reuse is earned.

The current policy safely passes all opaque continuations through, but can only
compress a standalone tool-output-only subscription payload. This leaves a
safe opportunity unexercised: a fresh, structurally simple current output tail
without opaque state.

## Design

### Subscription classifier

Retain the existing subscription classifier as the single authority. It emits
one of three outcomes:

1. `passthrough` for remote compaction, `previous_response_id`, opaque
   continuation content, malformed item lists, and non-output item types.
2. `tool_outputs_only` when every input item is a validated output item and
   every output is string-valued.
3. `mutable_tail_only` when the payload has exactly one final eligible
   string-valued output item, no opaque continuation indicators, and every
   earlier item is preserved unchanged.

`mutable_tail_only` is deliberately narrow. It does not permit tool-schema
compaction, model changes, request-override injection, semantic deduplication,
memory injection, or edits to earlier input items.

### Mutation and validation

For `mutable_tail_only`, construct a candidate by compressing only the final
output string through the existing content-router path. Validate before
forwarding:

- top-level keys and all non-tail items are structurally identical;
- the final item's type, `call_id`, tool name, and all non-output metadata are
  unchanged;
- the replacement is a string and is strictly smaller by provider token count;
- serialized candidate bytes are smaller than serialized original bytes.

Any failed classification, compressor error, failed validation, or non-saving
candidate returns the original payload. The proxy remains fail-open for the
request, while recording a precise decline reason.

### Cache contract

The feature never changes historical input items. For a repeated request,
every item before the final output item must compare equal before and after the
candidate mutation. This makes prefix stability an explicit test invariant;
we do not infer it from an observed cache hit.

Opaque continuation payloads remain whole-envelope passthrough. The feature
does not attempt to recompress a tail from an earlier request and never changes
an already-forwarded payload.

### Telemetry

Existing request-history fields record `transforms_applied`, direct saved
tokens, and the savings source. Add a distinct decline reason when a payload
is eligible-shaped but its tail mutation fails validation or does not save
tokens. No dashboard, credential, or runtime configuration change is part of
this scope.

## Testing and evidence

Test-first coverage will prove:

1. An opaque continuation carrying an otherwise compressible tool output is
   forwarded unchanged.
2. A valid fresh current output tail is compressed and only its `output`
   changes.
3. A historical output item is never changed when a later tail is selected.
4. A candidate that enlarges the serialized payload or fails token reduction
   is rejected and returns the original payload.
5. WebSocket first-frame and subsequent-frame dispatch uses the same policy.

The existing hermetic fake-upstream WebSocket harness will verify bytes sent
upstream. It is protocol-level evidence only: a real ChatGPT subscription
pilot is explicitly out of scope until the hermetic invariants pass.

## Rollout and rollback

The code path is fail-open at the request level. Reverting the branch returns
to current whole-envelope passthrough behavior. No restart, active-session
interruption, credential write, or configuration migration is required by this
change.

## Non-goals

- Compressing remote compaction or encrypted continuation objects.
- Rewriting historical conversation entries.
- Altering model-routing decisions on ChatGPT subscription transport.
- Changing provider cache keys or cache-control markers.
- Enabling/installing Kompress in the managed runtime.
