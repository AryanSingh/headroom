# Model routing and multi-provider commercial product assessment

**Date:** 2026-07-18
**Scope:** Headroom/Cutctx model routing, orchestration, provider adapters,
tests, and operator surfaces.

## Executive summary

The strongest safe commercial direction is a governed model-policy control
plane for coding agents. Cutctx already has conservative complexity routing,
capability and transport proof, deterministic workload contracts, model and
account discovery, route simulation, decision receipts, and staged lifecycle
controls. Those primitives can support three distinct products:

1. **Safe Savings** for conservative, exact-route optimization.
2. **Routing Studio** for governed workloads, simulation, evidence, and
   promotion/rollback.
3. **Workflow Governance** for explicit, approval-gated multi-provider
   workflows once execution uses the canonical data plane.

The product should not promise invisible “best model per task” provider
hopping. Compatibility requests intentionally fail closed when provider,
account, credential, capability, or transport proof is absent. That behavior
is commercially valuable trust infrastructure, not a limitation to bypass.

## Current-state assessment

| Capability | Status | Evidence | Commercial implication |
|---|---|---|---|
| Complexity-based cost routing | Production-oriented, opt-in | `cutctx/proxy/model_router.py`, routing preset and quality tests | Package as conservative savings, not autonomous task routing. |
| Capability-safe exact routes | Strong | `infer_request_capabilities`, `prepare_model_routing`, router tests | Capability proof is a differentiator and must remain non-bypassable. |
| Subscription/account transport guard | Strong | `downgrade_blocked_unproven_transport` and account mismatch tests | Prevents unsafe silent substitution on subscription transports. |
| Explicit role and selector routing | Implemented control plane | `cutctx/orchestration/models.py`, `engine.py` | Supports declared planning/implementation/review roles; does not infer arbitrary prompt intent. |
| Multi-provider catalog, including OpenCode Go | Implemented | `cutctx/orchestration/providers.py` and provider tests | Catalog availability does not make every compatibility endpoint cross-provider executable. |
| Cross-provider compatibility assignment | Intentionally unavailable | `transport_mismatch` and legacy proxy refusal tests | Keep fail-closed; do not market transparent provider hopping. |
| Contract lifecycle and simulator | Strong substrate | contracts, contract store, simulator, Routing Studio UI | Package starter contracts and readiness checks without changing selection semantics. |
| Planning-to-implementation workflow primitive | Controlled/development | workflow service and tests | Production execution still needs a canonical provider-neutral executor and transactional multi-host state. |
| Routing evidence and savings attribution | Strong | decision receipts, request outcomes, dashboard reports | Sell policy compliance and prevented unsafe routes alongside savings. |

## Prioritized opportunities

### Implemented now — Guided Safe Savings

The first safe slice is implemented as an opt-in explanation and rollback
experience over the existing router:

- a privacy-safe shared status schema with exact low/medium routes, transport
  posture, and recent applied/retained decision evidence;
- an authenticated read-only
  `GET /v1/orchestration/safe-savings/status` endpoint;
- `cutctx routing status`;
- a feature-gated dashboard panel;
- a confirmed Off action that reuses the authoritative
  `{"orchestrator_mode":"off"}` configuration mutation.

`CUTCTX_SAFE_SAVINGS_EXPERIENCE` controls discoverability only. It does not
enable routing, make provider calls, alter credentials, or relax capability,
account, and transport gates.

This makes the existing routing preset commercially legible: customers can
see exactly what is eligible, understand why a request stayed on its requested
model, and return to Off without editing configuration manually.

### Now — Routing Studio starter packs

Ship curated, editable draft contracts for implementation, review, and
research. A policy-readiness checklist should require model discovery,
capability declaration, route simulation, account/transport proof, and a
no-call preview before promotion. Templates must remain draft-only until the
existing evidence and lifecycle gates pass.

Target buyers are platform engineering and AI enablement teams with multiple
approved providers or models. The safest commercial model is a Business
control-plane feature priced by workspace or governed workload volume.

### Next — Explicit plan-to-implement templates

Generate two explicit tasks—a planning task and an implementation task—with a
typed plan artifact, declared dependency, route preview, and provider/account
requirements. Require user approval before implementation. Execution remains
disabled by default until workflow tasks traverse the same compression,
firewall, audit, rate-limit, credential, streaming, and outcome path as
compatibility traffic.

This addresses Claude-plans/OpenCode-Go-implements without pretending an
inbound Claude request can safely be replayed through another provider.

### Next — Evidence-backed recommendations

Use existing telemetry to draft recommendations containing the observed
workload shape, approved candidate, projected marginal savings, sample and
quality boundaries, and a draft contract. Never auto-promote. Abstain when
evidence, capability declaration, account proof, or transport proof is
insufficient.

### Later — Production multi-provider workflow executor

Introduce a provider-neutral executor boundary and transactional multi-host
workflow state only as an architectural project. Preserve provider/account
proof, compression, firewall, audit, outcomes, cancellation, retry bounds,
streaming rules, and tenant isolation.

### Do not pursue yet

- Invisible cross-provider “best model” hopping for arbitrary compatibility
  requests.
- Autonomous prompt-intent classification as binding policy.
- Automatic contract promotion from inferred quality signals.
- Provider-family wildcards or fallbacks that change model identity without
  explicit operator control.

## TDD and BDD delivery boundaries

Safe Savings acceptance scenarios include:

- Given a configured exact route and an applied trace, status shows the exact
  source/target, confidence/signals, transport posture, and applied reason.
- Given missing capability or transport proof, the requested model is retained
  and the stable reason is visible without a bypass control.
- Given routing is Off, status reports that requests retain their requested
  model and invents no route or decision evidence.
- Given the operator confirms Off, the existing mutation is called and the UI
  changes only after authoritative acknowledgement.
- Given the mutation fails, the enabled display remains and an actionable
  error is shown.

Regression coverage includes known and unknown reason codes, legacy partial
metadata, immutable status reads, endpoint authentication, CLI malformed/error
responses, browser-level enabled/hidden/Off flows, model router and preset
tests, routing quality benchmarks, and compatibility handlers.

Routing Studio starter packs must additionally prove draft-only creation,
capability and account validation, no-call simulation, revision conflict
handling, evidence-gated promotion, rollback, plaintext credential rejection,
and preservation of synthesized legacy contracts.

## Implementation evidence

The Guided Safe Savings implementation was verified on the isolated
`codex/guided-safe-savings-mode` branch with:

- **243 passing** focused Python tests covering the shared status model,
  authenticated orchestration API, CLI, dashboard integration, model router,
  presets, routing quality benchmark, Codex routing, and eight browser-level
  Orchestrator/Safe Savings scenarios;
- **389 passing, 27 skipped** broader CLI and OpenAI/Anthropic/Gemini
  compatibility tests;
- **43 passing** Responses compaction, compression-failure policy, and Codex
  WebSocket timeout regressions;
- **6 passing** packaged-dashboard asset and sync checks;
- **12 passing** dashboard frontend and JavaScript bundle-budget tests;
- Ruff on the changed Python/status/test surfaces;
- focused mypy with imports skipped on the two new typed modules;
- dashboard ESLint and a production Vite build.

The implementation also includes a regression for Codex Desktop HTTP
continuations: authenticated ChatGPT subscription requests below downstream
limits no longer receive a local 413 solely because compression timed out and
the request lacked a recognizable client header.

These are local and mocked compatibility tests. They are not evidence of
authenticated live-provider validation, contractual subscription approval,
SOC 2 certification, or production quality guarantees across every provider
and account type.

## Decision log

### Assumptions

- Commercial potential means increasing adoption or willingness to pay while
  retaining quality, safety, and operator trust.
- Existing open-core and commercial licensing boundaries remain unchanged.
- Provider selection and contract promotion remain explicit operator choices.

### Open questions

1. Which segment has demonstrated demand first: developer savings, platform
   governance, or enterprise multi-provider workflow control?
2. Which provider/account combinations can the production embedding prove at
   the compatibility boundary today?
3. Which customer outcome signals are reliable enough for evidence gates?
4. What transactional backend and tenancy model will support multi-host
   workflow execution?
5. Which live provider-backed benchmark and subscription-term evidence can
   support commercial quality or savings claims?
