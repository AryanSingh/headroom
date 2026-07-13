# Harness-aware routing and operator visibility

## Decision

Headroom will keep routing deployment-scoped and fail closed at the proxy
transport boundary. It will not infer that a model is usable merely because a
different provider or coding harness exposes an identically named model.

The product will make its existing harness compatibility contract visible in
the Orchestrator, alongside the deployment catalogue. This supplies an
operator with the answer to three separate questions that are currently easy
to conflate:

1. Is this model deployment configured and executable?
2. Does it meet the requested capabilities?
3. Can this request harness use this routing path safely?

## Scope

- Add a read-only **Harness compatibility** view to the orchestration studio.
- Fetch and display the authenticated compatibility manifest for Codex, Claude
  Code, and OpenCode, including support level, routing support, artifact
  handoffs, hidden-session isolation, and an explanatory note.
- Link the view to the existing model catalogue so operators can distinguish
  deployment availability from harness compatibility.
- Preserve the existing model router's transport/account checks. Cross-provider
  execution remains blocked on legacy proxy paths until a request/response
  adapter proves equivalent semantics.

## Non-goals

- Do not silently reroute an Anthropic wire request to an OpenAI transport, or
  vice versa.
- Do not create vendor/model aliases or cross-harness presets based on pricing
  alone.
- Do not perform provider calls merely to render this UI.

## Routing rules

Mixed harness operation is allowed only through a compatibility contract:

1. The incoming harness is identified.
2. The requested feature set is normalized to required capabilities.
3. A target deployment must be configured, enabled, and capability eligible.
4. The proxy must have a verified adapter for the incoming protocol and the
   selected deployment's transport.
5. Fallback is allowed only before the first response byte; a stream never
   changes providers mid-response.

The current runtime already enforces items 3--5 for legacy proxy routing.
This change makes the operator-facing contract discoverable; it does not
weaken the guard.

## UX

The Orchestration Studio gains a sixth tab after Models: **Harnesses**. Each
harness appears as a compact card with a support-level badge, a clear routing
status, artifact-handoff status, session-isolation status, and the contract
note. The intro calls out that a green harness card means the gateway path is
supported, not that every configured deployment is compatible.

The Models tab remains the source of truth for individual deployment
availability. The two views are deliberately separate to avoid implying a
cross-product compatibility matrix that the runtime has not verified.

## Tests and verification

TDD sequence:

1. Add a browser test that requires the harness manifest request and cards;
   run it and observe the expected failure.
2. Implement the smallest UI fetch/rendering change; rerun the browser test.
3. Add the manifest-request failure case to ensure a failed optional endpoint
   does not hide model/routing controls; implement and rerun.
4. Run the orchestration API/platform suite, dashboard build/lint, and the
   focused Playwright suite.

## Competitive gap assessment

LiteLLM provides mature deployment selection: weighted, rate-limit-aware,
least-busy, latency, cost routing, cooldowns, fallbacks, traffic mirroring,
and pre-call checks. Its routing documentation is the benchmark for
operational reliability. Headroom already has the beginnings of a stronger
safety layer: policy constraints, capability manifests, receipts, shadow
evidence, and a pre-first-byte fallback rule. The missing operator feature is
visibility into harness semantics. This scope closes that visibility gap while
keeping the existing safety boundary intact.

Sources: [LiteLLM routing documentation](https://docs.litellm.ai/docs/routing),
[Headroom harness contract](../../../cutctx/orchestration/harnesses.py), and
[Headroom proxy transport checks](../../../tests/test_orchestration_platform.py).
