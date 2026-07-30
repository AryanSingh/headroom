# Codex live-zone compression design

## Goal

CutCtx must reduce real input tokens for Codex/OpenAI Responses traffic without
giving up provider prompt-cache reuse or mutating opaque continuation state.

## Decision

Adopt a live-zone compression invariant for the OpenAI Responses subscription
path. On every request, CutCtx may transform only newly introduced,
mutable tool-result text before it is forwarded upstream. Once forwarded, that
rendered form is frozen: future requests must render it byte-for-byte
identically.

This follows the useful property of Headroom's live-zone model, but is
implemented within CutCtx's existing protocol-aware Responses handler and
retrieval infrastructure.

## Scope

Eligible content is the textual payload of fresh `function_call_output`,
`local_shell_call_output`, and `apply_patch_call_output` items, subject to the
existing provider-contract checks. The content router chooses a deterministic
strategy for logs, structured data, source code, and patches. A transform is
used only when it materially reduces tokens and satisfies its fidelity
contract.

For code, the first implementation uses CutCtx's reversible code compressor:
the visible skeleton remains valid and imports, signatures, annotations,
docstrings, module-level statements, and nested declarations remain visible.
Elided bodies are stored in CCR and represented by stable retrieval markers.

## Non-goals and invariants

- Never rewrite a user or assistant message, a `reasoning` item, a tool-call
  argument, or a remote-compaction item.
- Never alter an item already present in an opaque `previous_response_id`
  continuation or any other frozen prefix.
- Never emit an unstable marker, session-dependent rendering, or a transform
  that increases the payload.
- Never claim a compression saving if the transformed payload was not sent
  upstream.
- Preserve the current pass-through behavior for unsupported item shapes and
  for transforms that do not meet their acceptance contract.

## Flow

1. The Responses handler classifies the request as a subscription-safe mutable
   tail or an opaque continuation.
2. It extracts only eligible fresh tool-result text units from that mutable
   tail.
3. The content router applies a deterministic, reversible transform when it
   meets the relevant compression and fidelity gates.
4. CutCtx records the transformed form, strategy, input/output tokens, and
   retrieval reference in the decision receipt.
5. The compact output is forwarded to OpenAI and becomes the cacheable frozen
   form for later turns.
6. Later turns leave that prefix untouched; retrieval remains available if the
   model needs an elided original.

## Error handling and observability

Any classification uncertainty, unsupported shape, failed fidelity validation,
or missing retrieval backing must fail closed to the original text. The
diagnostic reason must distinguish `protected`, `unsupported`, `not_eligible`,
and `no_material_change`, rather than reporting all no-op cases as
compression failures.

Dashboard and receipt telemetry must separately show direct compression tokens
and provider-cache-protected tokens. A request with both is a successful result,
not a double count.

## Verification

Tests will prove all of the following:

1. A fresh Codex function-call output containing source code is compacted when
   reversible code compression is enabled.
2. Repeating the same turn keeps the transformed prefix identical and retains
   the provider cache-eligibility signal.
3. An opaque `previous_response_id` continuation is passed through unchanged.
4. User, assistant, reasoning, and tool-call argument content is unchanged.
5. Rejected or unbacked transforms fall back exactly to the original payload.
6. Receipts report direct compression and cache protection separately and
   accurately.

## Success criteria

For a representative multi-turn Codex Responses fixture with large code or
patch tool output, CutCtx records nonzero direct compression on the first
eligible turn and preserves a stable transformed prefix on the next turn. The
full OpenAI Responses compatibility suite remains green.
