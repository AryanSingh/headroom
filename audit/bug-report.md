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

---

# Orchestrator mode changes trigger a blocking page reset

## Severity

High. The write succeeds, but the UI looks broken for long enough that users
reasonably conclude the mode cannot be changed.

## Reproduction

1. Open the authenticated Orchestrator dashboard in Aggressive mode.
2. Click Balanced.
3. Observe the page during the subsequent refresh.

## Expected

The selected control stays visible, shows pending or confirmed state, and the
rest of the Orchestrator remains usable while fresh stats arrive.

## Actual

The mode POST succeeds, then global loading replaces the complete Orchestrator
with a loading panel. In the live reproduction, stats and health took up to
11.8 and 13.4 seconds respectively.

## Evidence

- Live browser reproduction confirmed the backend changed to `balanced` with
  preset `codex-gpt54mini-high`.
- `dashboard/src/lib/dashboard-context.jsx` sets `loading=true` on every
  `refresh()`.
- `dashboard/src/pages/Orchestrator.jsx` returns early while loading.

## Suggested fix

Separate initial blocking load from background refresh, preserve existing data
during refresh, and keep the optimistic control mounted until confirmed state
is available.

---

# Workload contracts are gated by unrelated stats and health requests

## Severity

High. A healthy feature endpoint appears unavailable because its component is
not mounted until unrelated dashboard data finishes.

## Reproduction

1. Reload the authenticated Orchestrator while stats or health is slow.
2. Observe when Routing Studio mounts and when its contracts request begins.

## Expected

Routing Studio starts its own request independently and reports its own loading,
empty, or error state.

## Actual

The parent returns early until global stats and health finish. The contracts
request does not start during that interval.

## Evidence

- Live `GET /v1/orchestration/contracts` returned 200 in about 649ms once
  mounted.
- Initial stats and health requests took about 11.8s and 13.4s.
- `Orchestrator.jsx` renders neither studio while global loading is true.

## Suggested fix

Render the Orchestrator feature shell independently from global refresh state
and let each studio own its loading lifecycle.

---

# Routing Studio has no timeout or recovery action for a hung contract request

## Severity

Medium. A network stall can leave a permanent loading state with no explanation
or recovery.

## Reproduction

1. Leave `GET /v1/orchestration/contracts` pending indefinitely.
2. Open the Contracts workspace.

## Expected

After a bounded timeout, show a clear error and Retry action.

## Actual

`loading` remains true until the promise settles. There is no abort timeout or
retry control.

## Evidence

- `RoutingStudio.jsx` only clears loading in the request `finally`.
- `routing-studio/api.js` supplies no timeout or abort signal.

## Suggested fix

Add a bounded request timeout and retryable loading state with stale-request
cancellation.

---

# First-run contract list is empty when no legacy roles exist

## Severity

Medium product gap.

## Reproduction

1. Start with an empty durable contract store.
2. Use orchestration config with zero roles.
3. Request `GET /v1/orchestration/contracts`.

## Expected

Pending product decision: either expose a starter contract or make the
intentional empty-state workflow unmistakable.

## Actual

The API returns an empty contract list, which users can interpret as contracts
failing to load.

## Evidence

- Live API returned `{"contracts":[],"revision":0}`.
- Live orchestration config has zero roles and bindings.
- `OrchestrationService.list_contracts()` synthesizes contracts only from
  configured legacy roles.

## Suggested fix

Choose and test one first-run policy: seed a built-in starter draft, expose
templates separately, or strengthen empty-state onboarding.
