# Model routing & multi-provider commercial product assessment

**Date:** 2026-07-18
**Scope:** read-only assessment of the current Headroom/Cutctx repository.
**Validation:** `tests/test_model_router.py`, `tests/test_model_router_presets.py`,
`tests/test_model_routing_quality_benchmark.py`, `tests/test_orchestration_contracts.py`,
`tests/test_orchestration_platform.py`, and `tests/test_orchestration_workflow.py` — **220 passed**.

## Executive summary

The strongest safe commercial direction is **Routing Studio for governed
coding-agent workloads**: a paid control plane that lets a team explicitly
declare the model/provider allowed for a named workload (implementation,
review, research, test), simulate the decision without a provider call, and
promote it through shadow and canary states with an auditable receipt.

This is more credible than marketing an autonomous “best model for every task”
promise. The repository already has the necessary primitives: provider
accounts with encrypted credentials, capability-aware deterministic role
bindings, workload contracts, a route simulator, decision traces, and
quality/evidence gates. The safe near-term addition is to package these as a
guided policy product—not to introduce silent cross-provider switching.

The proposed initial package should keep all provider changes **explicit**:
an operator selects the approved provider/model per workload; Cutctx proves
the compatible account and transport before execution; and only same-model
equivalent deployments are automatically selected. Existing optimization
routing remains separately opt-in and conservative.

## Current-state assessment

| Capability | Evidence | Readiness | Limitation / product implication |
|---|---|---|---|
| Complexity-based cost routing | `cutctx/proxy/model_router.py`; `docs/content/docs/model-routing-presets.mdx` | Production-oriented opt-in | It routes only exact, prevalidated models. High-risk, code, tool, reference-dependent, and complex requests retain the requested model. It is not general task-intent orchestration. |
| Capability-safe routing | `infer_request_capabilities` and `prepare_model_routing`; tests assert `target_missing_capabilities` | Strong | A target must declare all required features (tools, structured output, vision, audio, streaming). This is a commercial trust advantage and must remain non-bypassable. |
| Subscription/compatibility transport guard | `prepare_model_routing`; tests cover `downgrade_blocked_unproven_transport` | Strong | Arbitrary target models are blocked on unproven subscription transports. This reduces “zero-config” routing coverage but prevents harmful silent substitution. |
| Explicit role + selector routing | `cutctx/orchestration/models.py`, `engine.py`, `docs/.../orchestration-platform.mdx` | Production-oriented control plane | Roles are explicit. The engine does not infer that an arbitrary prompt is planning versus implementation. |
| Multi-provider provider catalog | `cutctx/orchestration/providers.py`; OpenCode Go catalog entry and tests | Implemented | Provider availability does not make every compatibility endpoint cross-provider executable. Account and wire-mode proof still applies. |
| Cross-provider request assignment through compatibility endpoints | `model_router.py`; tests `test_legacy_proxy_refuses_cross_provider_assignment` | Intentionally unavailable | Fails closed with `transport_mismatch`. This is correct; do not sell it as transparent provider hopping. |
| Durable planning → implementation workflow primitive | `cutctx/orchestration/workflow.py`; workflow tests | Development/controlled deployment | Local JSON/file-lock store is single-host or shared POSIX volume only. `/execute` and workflow `/run` are explicitly development opt-in because they bypass the canonical proxy pipeline. |
| Contract lifecycle and route simulator | `cutctx/orchestration/contracts.py`, `contract_store.py`, `dashboard/src/components/routing-studio/` | Strong product substrate | Lifecycle state and no-call preview exist, but the customer journey needs presets, guided setup, and outcome instrumentation to be commercially legible. |
| Shadow calibration and learned routing confidence | `model_routing_evals.py`, `model_routing_training.py`, benchmarks | Evidence-gated / experimental | Shadow replay is deliberately constrained; a calibrated Claude three-tier preset abstains until a promoted artifact exists. Do not position adaptive cross-provider selection as ready. |
| Observability and savings attribution | `README.md`; decision trace, executions, dashboard studios | Strong | Savings are well differentiated, but product messaging should expose policy compliance, prevented unsafe routes, and quality evidence—not only dollars saved. |
| Enterprise governance | `cutctx_ee`, `PRODUCT_GUIDE.md` | Commercial substrate | The repository itself notes external validation remains necessary for SOC 2 and similar claims. Avoid claiming certifications that are not available. |

## What is working and should be packaged

### 1. Conservative optimization routing

`codex-gpt54mini-high` keeps high-complexity work on the requested model,
routes clearly simple GPT work to `gpt-5.4-mini`, and uses a declared medium
tier when available. Claude routes are within the Claude family. The router
recognizes recent provider-native tool use, code, multimodal content,
reference-dependent context, and high-risk language as gates against a
downgrade. The quality benchmark has zero tolerated unsafe Mini downgrades.

This should be packaged as **Safe Savings Mode**, not as a universal router:
the buyer gets measurable savings while retaining model choice for real agent
work. Its commercial proof is the existing per-source savings accounting.

### 2. Deterministic workload contracts

Contracts provide immutable intent with capabilities, provider/account/data
constraints, budget/reliability objectives, lifecycle states (`draft`,
`shadow`, `canary`, `active`, `paused`, `retired`), and a no-call simulator.
That is an unusually strong foundation for an enterprise-safe policy product.

This should be packaged as **Routing Studio**, initially for three high-value
templates: implementation, code review, and research. The existing UI already
contains those templates, a simulator, evidence view, and rollout controls.

### 3. Explicit, controlled multi-provider roles

The orchestration engine can bind a `planner` role to Anthropic and an
`implementer` role to OpenCode Go or OpenAI. Binding selection is deterministic
by role and selectors; strict mode refuses an unavailable, incompatible, or
unprovable target. Equivalent deployments can be selected automatically, but
only for the same provider/model identity.

This supports a differentiated offer: **bring your model accounts, apply
workload policy, and retain account isolation**. It should not yet be called
an autonomous multi-agent manager.

## Prioritized opportunities

### Now — Guided “Safe Savings Mode” for coding agents

**Buyer/user:** individual developers, engineering teams using Claude Code,
Codex, or OpenCode.
**Commercial model:** Team add-on or usage/value-based routing tier; use the
existing savings report as the value meter.
**Smallest safe slice:** turn the existing canonical routing preset into a
guided dashboard/CLI setup that shows: eligible exact model pairs, current
mode, why each request stayed put, and a one-click rollback to `off`.

**Why it matters:** it converts a technically sound, opt-in router into a
legible purchase: “save on clearly safe work, preserve your chosen model for
agentic work.” It is deployable without new provider credentials or
cross-provider execution.

**Do not add:** automatic family wildcards, a heuristic that assumes all
short prompts are safe, or silent use of unproven subscription transports.

**Status: implemented (2026-07-18).** The smallest safe slice above shipped as
the guided Safe Savings experience behind `CUTCTX_SAFE_SAVINGS_EXPERIENCE`
(discoverability only; routing remains separately opt-in):

- `cutctx/proxy/safe_savings_status.py` — pure status/explanation model
  (16 unit tests, including one stable-copy test per terminal decision
  reason and mutation-safety assertions).
- `GET /v1/orchestration/safe-savings/status` — authenticated read-only
  endpoint plus live-proxy wiring (endpoint auth/read-only/503 tests and a
  live-state integration assertion).
- `cutctx routing status` — read-only CLI summary (3 tests: Off, enabled
  routes/decision/confidence rendering, auth failure without key leakage).
- Dashboard Safe Savings panel with confirmed rollback to
  `{"orchestrator_mode": "off"}` via the existing config mutation (4
  Playwright tests: applied, blocked-without-bypass, Off action asserting
  the exact mutation body, and mutation-failure retention).

Verified gates on 2026-07-18: focused regression set 229 passed
(`test_safe_savings_status`, `test_safe_savings_docs`,
`test_cli/test_routing_status`, `test_orchestration_platform`,
`test_dashboard_orchestrator`, `test_dashboard_orchestrator_policy_e2e`,
`test_model_router`, `test_model_router_presets`,
`test_model_routing_quality_benchmark`); broader compatibility gates 387
passed / 27 skipped (`tests/test_cli`, Codex routing, OpenAI Chat/Responses
shadow routing, Anthropic routing, Gemini integrations); ruff clean and mypy
clean on the new modules; dashboard lint and single-bundle build clean.

**Coverage caveat:** all provider paths in these suites run against mocked
backends, intercepted browser routes, or patched HTTP clients. No
authenticated live-provider validation (OpenAI, Anthropic, Gemini, or Codex
subscription transports) was performed as part of this change.

### Now — Routing Studio starter packs for governed teams

**Buyer/user:** platform engineering, AI enablement, and engineering leaders
with more than one approved provider/model.
**Commercial model:** Business plan control-plane feature; price by workspace,
operator seats, or governed agent/workload volume.
**Smallest safe slice:** ship curated, editable contracts for `implementation`,
`review`, and `research`; add a “policy ready” checklist that requires model
discovery, required capability declaration, route simulation, and a no-call
preview before a contract can be promoted.

**Why it matters:** the current primitives are already in the UI and API. The
product work is safely additive and makes controls discoverable rather than
changing routing semantics.

**Dependency:** articulate the deployment/account proof requirements in the
UI before a customer attempts a compatibility-route assignment.

### Next — Explicit plan → implement workflow templates, with user approval

**Buyer/user:** high-usage coding teams that deliberately allocate different
models to design and execution.
**Commercial model:** premium “agent workflow governance” package, initially
for self-hosted/lighthouse customers.
**Smallest safe slice:** a non-executing workflow template generator that
creates two explicit tasks: `planning` and `implementation`, passes the plan
as a declared artifact, and exposes the route preview and provider/account
requirements for each task. Execution remains disabled by default.

**Why it matters:** it addresses the Claude-plans/OpenCode-implements use
case without pretending an inbound Claude protocol request can safely be
replayed through a different provider.

**Risk/dependency:** production execution needs a canonical, provider-neutral
executor that traverses the same compression, firewall, audit, rate-limit, and
outcome path as compatibility traffic. The current direct executor is clearly
documented as a development diagnostic, and the local workflow store is not a
multi-host scheduler.

### Next — Evidence-backed routing recommendations, never auto-promotion

**Buyer/user:** FinOps/AI platform teams with enough volume to optimize model
policy by workload.
**Commercial model:** Business/Enterprise analytics module.
**Smallest safe slice:** generate a recommendation that states: observed
workload shape, approved candidate models, projected marginal savings,
evidence sample count/quality boundary, and a draft contract. An operator
must simulate and explicitly promote it.

**Why it matters:** it monetizes the existing routing evidence and outcome
telemetry while keeping humans responsible for provider choice. It is a safer
and more defensible promise than “AI automatically chooses the best model.”

**Gate:** do not generate recommendations when evidence is insufficient,
quality-blocked, missing capability declarations, or based on a client whose
transport cannot prove the target account.

### Later — Production multi-provider workflow executor

**Buyer/user:** enterprise platforms running multi-step AI workflows.
**Commercial model:** Enterprise deployment/control-plane module.
**Scope:** create a canonical executor boundary for workflow tasks, preserving
auth/account proof, compression/firewall/audit/outcome behavior, streaming
rules, and durable storage. Replace the single-host JSON workflow state store
with a transactional shared backend when supporting multi-host workers.

**Why later:** this is valuable but architectural. Shipping it prematurely
would create the exact regression risk the current fail-closed design avoids.

### Do not pursue yet — invisible “best model per task” cross-provider hopping

The evidence does not support transparently taking an arbitrary Claude/Codex
compatibility request and sending it to a different provider. It conflicts
with current account/transport safety contracts and complicates credentials,
tool wire formats, subscription terms, auditing, and stream behavior. Keep
provider choice explicit until a canonical executor can prove all boundaries.

### Do not pursue yet — autonomous prompt intent classification as policy

Task-type inference can be a non-binding suggestion, but it must not select
providers or contracts directly. Intent is too ambiguous for a billing,
security, and quality control plane; explicit roles/selectors and an operator
review are the right default.

## Recommended product direction

Position Headroom/Cutctx as the **governed context and model-policy control
plane for coding agents**, with three separately understandable products:

1. **Safe Savings** — opt-in, conservative same-family/model routing with a
   precise savings attribution report.
2. **Routing Studio** — contracts, simulation, evidence, canary/pause/rollback,
   and policy receipts for teams that bring their own approved accounts.
3. **Workflow Governance** (lighthouse/Enterprise) — explicit, approval-gated
   multi-step task templates once their execution can use the canonical data
   plane.

Automate only these decisions:

- selection among explicitly declared equivalent deployments of the same model;
- safe cost routing where a provider-validated exact route, capability proof,
  and transport proof all succeed;
- evidence aggregation, warnings, and draft-policy recommendations.

Keep user/operator controlled:

- choice to use another provider or account;
- role/task boundaries and plan-to-implementation handoff;
- contract promotion and rollback;
- any fallback that changes model identity;
- data classification, allowed provider/account/region constraints, and budget
  ceilings.

## TDD / BDD delivery plan

### Opportunity A: Guided Safe Savings Mode

**Smallest slice:** a read-only eligibility/explainability panel and CLI
summary for the existing preset; no new route logic.

**BDD acceptance scenarios**

- Given a supported source model and a simple, self-contained request, when an
  operator enables Safe Savings Mode, then the panel shows the exact target,
  confidence/signals, savings basis, and applied status.
- Given code, a tool call/result in the recent window, missing target
  capabilities, or unproven subscription transport, when the request is
  evaluated, then the requested model remains unchanged and the panel shows
  the specific retention reason.
- Given the operator selects Off, when a new request arrives, then the request
  uses the originally requested model and no prior route state persists.

**TDD / regression matrix**

| Test class | Required coverage |
|---|---|
| Unit | Existing complexity, confidence, capability, and exact-route tests remain unchanged; add presentation mapping tests for every terminal decision reason. |
| Contract/API | Assert read-only state never changes `CUTCTX_MODEL_ROUTING`, route config, request model, or credentials. |
| UI | Dashboard test renders applied and blocked reasons without exposing a control that bypasses transport/capability guards. |
| Compatibility | OpenAI Chat/Responses, Anthropic Messages, Gemini, Codex subscription routes retain current request mutation rules. |
| Rollout | Feature flag off by default; snapshot route decisions before/after enabling the view must match byte-for-byte. |

### Opportunity B: Routing Studio starter packs

**Smallest slice:** built-in draft-only templates and a readiness validator;
do not change engine selection or automatic promotion.

**BDD acceptance scenarios**

- Given a team creates an implementation contract, when it omits a required
  capability or points to an undiscovered model, then it cannot advance beyond
  draft and explains the missing proof.
- Given a valid draft, when an operator runs the simulator, then no provider
  call occurs and the receipt identifies selected/rejected candidates,
  account, policy constraints, and worst-case deadline.
- Given a contract in shadow or canary, when evidence is below the configured
  minimum or violates the unsafe-rate limit, then it cannot be promoted and
  the active contract remains untouched.

**TDD / regression matrix**

| Test class | Required coverage |
|---|---|
| Unit | Validate each template, lifecycle transition, account-qualified deployment key, selector precedence, and provider allow-list intersection. |
| Negative/security | Reject plaintext credentials, ambiguous provider:model bindings, cross-provider compatibility assignment, unsupported capabilities, and data-policy broadening. |
| Integration | API → simulator → contract store path makes zero provider calls; revision conflicts and rollback preserve active policy atomically. |
| UI | Template creation is isolated in `draft`; promotion controls show evidence gate failures and do not hide rejected-candidate reasons. |
| Rollout | Templates behind a UI feature flag; existing legacy role bindings continue to synthesize legacy active contracts unchanged. |

### Opportunity C: Explicit plan → implement workflow template

**Smallest slice:** construct and validate a two-task workflow with a typed
plan artifact reference, route previews, and an explicit “not executable in
production yet” marker. No background execution.

**BDD acceptance scenarios**

- Given an operator selects a Claude planning account and an OpenCode Go
  implementation account, when the template is generated, then it creates two
  role-bound tasks with an explicit dependency and shows both account/transport
  constraints.
- Given a plan artifact has not been approved, when implementation is requested,
  then the implementation task remains pending and no provider is invoked.
- Given a compatibility request attempts to execute the implementation role
  through the wrong provider/account, when routed, then Cutctx rejects it with
  `transport_mismatch` or `account_transport_mismatch` and does not fall back.

**TDD / regression matrix**

| Test class | Required coverage |
|---|---|
| Unit | Workflow DAG validation, artifact schema/reference validation, selector/role binding resolution, idempotency keys, and no implicit provider change. |
| Integration | Task dependency ordering, lease fencing, cancellation, retry bounds, and first-byte streaming no-switch behavior. |
| Security | Artifact access policy, redaction, tenant/workspace boundary, account credential non-disclosure, and cross-provider fail-closed routes. |
| Deployment | Direct execution endpoint remains disabled by default; multi-host execution is rejected/documented until a transactional backend is configured. |

## Decision log

### Assumptions

- “Commercial potential” means safely increasing willingness to pay and
  adoption, not merely adding provider logos.
- The existing commercial tiers and licensing boundary remain in scope; this
  assessment does not propose a pricing change to the open-core boundary.
- Tests demonstrate substantial behavioral coverage but are not substitute for
  authenticated end-to-end validation with every provider/account/transport.

### Open questions before implementation

1. Which target segment has demonstrated demand first: self-hosted engineering
   teams seeking savings, AI platform teams seeking governance, or enterprises
   seeking multi-provider workflow control?
2. Which provider/account combinations can the production embedding prove at
   the compatibility boundary today? This determines what can be offered as
   same-provider production routing versus a controlled workflow service.
3. What outcome signals can customers reliably provide for contract evidence
   (tests passed, PR merged, review accepted, human rating)?
4. What is the supported durable backend and tenancy model for a production
   workflow executor? The local JSON store is intentionally insufficient for
   distributed worker claims.
5. What live provider-backed benchmark matrix, subscription terms, and
   customer evidence are available to support a commercial quality/savings
   guarantee?

### Evidence used

- `docs/content/docs/model-routing-presets.mdx`
- `docs/content/docs/orchestration-platform.mdx`
- `cutctx/proxy/model_router.py`
- `cutctx/orchestration/{models,engine,contracts,contract_store,service,providers}.py`
- `dashboard/src/components/{OrchestrationStudio,routing-studio/*}.jsx`
- `README.md`, `PRODUCT_GUIDE.md`
- Targeted test run noted at the top of this report.
