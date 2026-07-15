# Model routing: `claude-sonnet-5` is not eligible

## Severity

High for users relying on aggressive model routing to reduce Claude Sonnet 5
costs. The proxy behaves safely (it does not select an unconfigured target),
but the UI mode implies a capability that the current route table cannot
provide for the observed traffic.

## Reproduction

1. Set the dashboard orchestrator/model-routing mode to **Aggressive**. This
   resolves to the `economy` preset.
2. Send an Anthropic request whose requested model is `claude-sonnet-5`.
3. Inspect Recent requests.

## Expected

For a low-risk request, a documented explicit downgrade route should change
the effective model; otherwise the dashboard should surface an actionable
`no_route_for_model` reason.

## Actual

The request remains on `claude-sonnet-5`. Directly exercising both bundled
presets returns:

```
economy: applied=False; reason=no_route_for_model; target=None
codex-gpt54mini-high: applied=False; reason=no_route_for_model; target=None
```

The `economy` route table includes `claude-sonnet-4-5` and older 3.5 Claude
identifiers, but no `claude-sonnet-5` source. `ModelRouter._find_route` only
performs an exact source-model match, so the requested model cannot route.

## Evidence

- Screenshot: every visible recent request is labelled `claude-sonnet-5`.
- `cutctx/proxy/model_router.py`: `economy_preset()` defines only 4.5/3.5
  Claude source routes; `maybe_route()` returns `no_route_for_model` when no
  exact source entry is found.
- Local direct routing check reproduced the returned reason for both presets.

## Suggested fix

Add an explicitly validated `claude-sonnet-5` downgrade mapping to the
appropriate supported target (and a matching exact-model regression test),
after confirming the upstream transport accepts that target. Also expose the
per-request routing-decline reason in the Recent requests UI so an unsupported
model is distinguishable from a disabled feature, bypass header, or
complexity-based abstention.

---

# ChatGPT subscription continuations fail after WebSocket disconnect

## Severity

Critical for long-running Codex tasks. A healthy task can lose its final answer
after many minutes of work, then enter a retry loop that alternates between a
local context refusal and an upstream HTTP 400.

## Reproduction

1. Run Codex through the CutCtx ChatGPT-subscription Responses WebSocket path.
2. Let a task accumulate roughly 194,000 model-reported input tokens and opaque
   `encrypted_content` continuation items.
3. End the live WebSocket before the final assistant message and allow Codex to
   rebuild the turn for retry.
4. Observe CutCtx's local JSON tokenizer estimate the rebuilt 944 KB frame at
   294,402 tokens against a 242,400-token refusal threshold.
5. Observe the WebSocket close with `context_refused`, followed by an HTTP
   fallback that routes `gpt-5.6-sol` to `gpt-5.6-luna` and receives HTTP 400.

## Expected

Opaque ChatGPT subscription continuation state remains on its requested model
and reaches ChatGPT unchanged. Approximate local token accounting may produce
telemetry, but it must not destructively truncate or reject data CutCtx cannot
interpret authoritatively.

## Actual

Session `019f6752-d143-7e70-b780-34396670b634` completed its live work at about
194,419 reported input tokens but emitted no final assistant message. The next
WebSocket retry was refused locally as 294,402 tokens. HTTP fallback then
changed the model and ChatGPT returned `400 Bad Request`.

## Root cause

- The Responses context guard tokenized serialized encrypted continuation data
  as ordinary prompt text, overestimating the authoritative model count by
  roughly 100,000 tokens.
- Subscription HTTP routing disabled implicit downgrades but still allowed
  transport-safe preset targets, so model-bound continuation state moved from
  `gpt-5.6-sol` to `gpt-5.6-luna`.
- The emergency truncator was allowed to rewrite opaque continuation state.

## Implemented fix

- Detect non-empty `encrypted_content` with a bounded, non-decoding shape walk.
- Preserve the requested model for ChatGPT-subscription HTTP requests, matching
  the existing WebSocket transport restriction.
- Treat local context refusals as advisory for opaque subscription
  continuations at the HTTP, first-frame WebSocket, compression-failure,
  no-op-compression, and post-compression boundaries.
- Preserve the existing fail-closed guards and routing behavior for ordinary
  API-key and non-opaque requests.

## Verification evidence

- Red/green regressions reproduce both the WebSocket refusal and HTTP fallback
  mutation.
- Focused routing/Responses suite: 127 passed.
- Broader OpenAI Responses suite: 170 passed, 14 skipped, zero failures.
- Ruff reports zero errors for the modified source and tests.
- Live isolated proxy smoke tests returned `CODEX_CUTCTX_OK`,
  `CLAUDE_CUTCTX_OK`, and `OPENCODE_CUTCTX_OK_2` through Codex CLI, Claude CLI,
  and OpenCode respectively.

## Suggested follow-up

Persist authoritative upstream usage by conversation and compare it with local
estimates in telemetry. Large estimator drift should be observable, but must
not become a destructive policy for opaque model-owned data.
