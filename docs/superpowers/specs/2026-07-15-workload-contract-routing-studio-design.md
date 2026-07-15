# Workload Contract Routing Studio Design

## Purpose

Headroom will become the routing control plane for coding-agent teams. Teams will define workload requirements, preview decisions, measure outcomes, and promote routing changes without giving an optimizer permission to bypass safety or compliance rules.

The current product exposes two routing systems:

- deterministic orchestration selects a model deployment from roles, bindings, capabilities, policies, and provider state;
- optimization routing classifies request complexity and may replace the requested model with a cheaper tier.

Both systems remain useful. The product needs one user-facing model that defines their order, scope, and evidence requirements.

## Product position

Headroom will sell verified cost reduction for coding-agent work under explicit quality, reliability, and policy constraints.

The initial buyer is an engineering leader or AI platform owner who operates coding agents across repositories and wants to control spend without increasing failed tasks, review load, or production risk.

Generic gateways route API calls by price, latency, provider health, or fixed fallback order. Headroom will route agent work using repository context, task type, tool activity, risk, capability requirements, and measured engineering outcomes.

## Design principles

1. Users express workload intent. Headroom compiles it into routing primitives.
2. Hard constraints run before optimization and cannot be weakened by learned policy.
3. The router abstains when evidence cannot prove that a cheaper candidate meets the contract.
4. Preview and live execution use the same decision engine and receipt schema.
5. Draft configuration never masquerades as live configuration.
6. A policy change moves through simulation, shadow, canary, and promotion.
7. Every decision remains explainable without storing prompt or response text.

## Primary domain object

### WorkloadContract

A versioned workload contract replaces the role as the main user-facing object. Existing roles remain accepted aliases during migration.

```text
WorkloadContract
  identity
    id
    name
    version
    description
    role_aliases

  matching
    task_types
    selectors

  requirements
    required_capabilities
    minimum_context_tokens
    minimum_output_tokens
    allowed_providers
    allowed_accounts
    allowed_regions
    allowed_data_classifications
    retention_policy

  objective
    type
    quality_floor
    maximum_cost_usd
    maximum_ttft_ms
    maximum_total_latency_ms
    weights

  reliability
    connect_timeout_seconds
    first_token_timeout_seconds
    attempt_timeout_seconds
    stream_idle_timeout_seconds
    total_deadline_seconds
    attempts_per_deployment
    maximum_deployments
    fallback_triggers
    maximum_fallback_cost_usd

  evaluation
    accepted_outcome_signals
    minimum_samples
    unsafe_quality_floor
    maximum_unsafe_rate
    canary_percentage
    automatic_rollback_conditions
```

The service stores immutable versions. A contract has separate draft, shadow, canary, active, paused, and retired states. Only one version may be active for a contract ID.

### Compatibility compilation

Headroom compiles each active contract into the existing orchestration structures:

- one role with the contract ID and required capabilities;
- one default binding and optional selector bindings;
- provider, residency, classification, and budget constraints;
- equivalent deployments and fallback candidates;
- optimization thresholds and scorer requirements;
- retry, timeout, cooldown, and fallback settings.

Existing role and binding configuration loads as a generated legacy contract. The migration preserves behavior until the operator changes or promotes a contract.

## Decision pipeline

Every preview and execution follows the same ordered pipeline.

### 1. Resolve request context

The router resolves:

- explicit contract or role alias;
- client and harness;
- repository and workspace identity hashes;
- task type;
- workflow, command, skill, and agent selectors;
- recent tool activity and context risk signals;
- request capabilities and protocol requirements;
- estimated input and output tokens.

The router records the source of each value. Organization and project policy may narrow caller input but cannot broaden it.

### 2. Resolve contract version

Live traffic uses the active contract version unless a canary assignment selects a canary version. Preview requests name the live or draft version explicitly.

The decision receipt includes the contract ID, version, lifecycle state, policy bundle hash, and canary cohort.

### 3. Apply hard eligibility rules

The safety kernel removes a candidate when it violates any of these rules:

- provider, account, region, or data policy;
- required model capability;
- harness or wire-protocol compatibility;
- context or output capacity;
- explicit allowlist or denylist;
- request cost ceiling;
- deprecation, disabled account, or unavailable deployment;
- active deployment cooldown;
- high-risk task retention rule;
- insufficient transport proof;
- contract rule that requires a named baseline model.

The optimizer never sees excluded candidates as selectable. The receipt records a stable rejection code and a plain-language explanation for every excluded candidate.

### 4. Choose a model objective

The contract selects one objective:

- `exact_assignment`: use the named model only;
- `lowest_cost_within_quality_sla`: minimize estimated total cost among candidates that meet quality and latency requirements;
- `lowest_latency_within_quality_budget`: minimize predicted latency among candidates that meet quality and cost requirements;
- `highest_quality_within_budget`: maximize measured outcome quality within the cost ceiling;
- `reliability_first`: prioritize completion probability, then latency and cost;
- `custom`: use explicit normalized weights after hard floors pass.

The UI no longer exposes `fastest`, `cheapest`, `highest_quality`, and `balanced` without definitions. The compatibility API maps old values to their closest compiled objective and marks the receipt as `legacy_policy_mapping`.

### 5. Evaluate evidence

Quality evidence comes from the most specific sufficiently populated segment:

1. contract and model pair;
2. task type and model pair;
3. client or harness and model pair;
4. repository hash and model pair;
5. global model pair.

A segment inherits a broader segment when it has too few samples. A segment that has enough samples but fails the quality floor becomes blocked. It does not inherit a more permissive global decision.

The router abstains when no evidence satisfies the contract. It selects the conservative baseline and records `insufficient_evidence` or `quality_blocked`.

### 6. Rank eligible models

The router estimates total request cost from expected input and output tokens. It uses outcome quality, completion probability, time-to-first-token percentiles, total latency percentiles, and price freshness.

The ranking result contains input values, timestamp, evidence sample count, confidence, and the objective calculation. The receipt never presents provider reliability as answer quality.

### 7. Select a deployment

After choosing a model, the router selects an approved provider/account deployment of that model.

Deployment selection may use:

- active health status;
- latency and throughput percentiles;
- rate-limit headroom;
- budget headroom;
- configured stable weights;
- region and account preference;
- cooldown state.

Changing provider or account for the same model counts as deployment selection. Changing model requires the model objective and evidence checks.

### 8. Execute within a reliability budget

The router replaces the single timeout with:

- connection timeout;
- first-token timeout;
- attempt timeout;
- streaming idle timeout;
- total request deadline;
- attempts per deployment;
- maximum deployments;
- fallback cost limit.

The contract compiler calculates the worst-case retry and fallback duration. It rejects a contract when the configured attempts cannot fit inside the total deadline.

Streaming requests may change deployment only before the first visible byte. After output begins, the service records a terminal stream failure and does not splice output from another model or deployment.

### 9. Emit receipt and collect outcome

Every execution produces a versioned receipt containing:

- request and contract identifiers;
- matching selectors and resolved context sources;
- policy bundle and contract version;
- eligible and rejected candidates;
- ranking inputs and evidence freshness;
- assigned model and selected deployment;
- retry and fallback history;
- predicted and actual cost and latency;
- transport compatibility proof;
- final result and linked outcome identifiers.

The outcome system accepts bounded signals such as task completion, CI result, pull-request acceptance, user rating, retry count, rollback, and manual override. Headroom stores hashes and normalized labels instead of repository content.

## Routing Studio information architecture

The Orchestrator page becomes Routing Studio. The primary navigation contains four workspaces.

### Contracts

The Contracts workspace lists workload contracts with:

- lifecycle state;
- active and draft versions;
- baseline model;
- objective summary;
- quality-safe savings;
- recent quality and reliability status;
- open alerts.

Creating a contract starts with coding-agent templates:

- Planning and architecture;
- Implementation;
- Testing and verification;
- Code review;
- Security review;
- Documentation;
- Fast background work.

The editor uses progressive disclosure:

1. intent and baseline;
2. quality, cost, and latency requirements;
3. capabilities and data policy;
4. reliability and fallback budget;
5. evidence and rollout settings;
6. compiled policy inspection.

Provider accounts, model discovery, harness compatibility, and advanced selector bindings remain accessible from contract fields and an Infrastructure section. They no longer dominate the first screen.

### Simulator

The Simulator previews a live or draft contract against a scenario.

A scenario may include role, task type, client, harness, selectors, capabilities, token estimates, data classification, and request ID. The simulator does not invoke a model by default.

The result shows:

- live versus draft decision;
- selected model and deployment;
- estimated cost, latency, and quality;
- matched contract and selector rule;
- every rejected candidate and reason;
- retry/fallback plan and worst-case deadline;
- evidence source and freshness;
- changed fields and expected impact.

Users can replay a privacy-safe sample of historical receipts through a draft. The batch result reports changed-route rate, estimated savings, quality coverage, SLA violations, and blocked segments.

The UI labels unsaved, draft, canary, and live configuration. Previewing a visible draft never calls the live-only route endpoint without the draft payload or version.

### Rollouts

The Rollouts workspace manages:

```text
Draft → Simulated → Shadow → Canary → Active
                     ↓          ↓
                   Paused ← Rolled back
```

Each gate has explicit entry requirements:

- simulation requires zero hard-policy violations;
- shadow requires a valid contract and compatible candidate coverage;
- canary requires minimum evidence and no blocked quality segment;
- promotion requires quality, unsafe-rate, latency, and savings thresholds;
- automatic rollback uses contract-specific error, quality, and SLA conditions.

Operators can pause or roll back immediately. Rollback reactivates the previous immutable version and produces an audit receipt.

### Evidence

The Evidence workspace answers:

- How much verified cost did Headroom save?
- Did quality change by contract, task type, repository, harness, or model pair?
- Which segments lack enough evidence?
- Which routes caused retries, fallbacks, or developer overrides?
- Why did Headroom abstain?
- Which policy version governed a decision?

The default financial metric is quality-safe savings. Raw routed savings remain available but do not lead the product.

## Interface behavior

### Decision pipeline visualization

Each preview and receipt shows the pipeline as six steps:

1. Contract
2. Constraints
3. Evidence
4. Model
5. Deployment
6. Execution

Selecting a step opens its inputs and results. The UI keeps the summary readable while giving operators complete evidence when needed.

### Responsive design

At small widths, the desktop sidebar collapses behind a menu button. The four Routing Studio workspaces use a horizontally scrollable or select-based subnavigation. Forms use one column, tables become labeled cards, and decision evidence does not require horizontal page scrolling.

The interface must satisfy WCAG 2.1 AA for reflow, contrast, focus visibility, keyboard operation, labels, error identification, and status announcements.

Tabs implement the WAI-ARIA tabs pattern with one active tab stop, arrow-key navigation, `aria-controls`, and named tab panels.

### Loading, stale, empty, and error states

The shell distinguishes proxy health from orchestration-data health. Each dataset includes a freshness timestamp. Stale data remains visible with a warning and cannot silently support promotion.

The product provides starter scenarios when a contract has no evidence or no configured deployments. A failed simulation retains the previous successful result and marks it stale.

Mutations use idempotency keys and optimistic concurrency. A save that conflicts with a newer server version shows a field-level diff instead of overwriting it.

## API boundaries

Add versioned resources:

```text
GET    /v1/orchestration/contracts
POST   /v1/orchestration/contracts
GET    /v1/orchestration/contracts/{id}/versions/{version}
PUT    /v1/orchestration/contracts/{id}/draft
POST   /v1/orchestration/contracts/{id}/simulate
POST   /v1/orchestration/contracts/{id}/shadow
POST   /v1/orchestration/contracts/{id}/canary
POST   /v1/orchestration/contracts/{id}/promote
POST   /v1/orchestration/contracts/{id}/pause
POST   /v1/orchestration/contracts/{id}/rollback
GET    /v1/orchestration/contracts/{id}/evidence
GET    /v1/orchestration/receipts/{request_id}
POST   /v1/orchestration/outcomes
```

The existing config, role, binding, route, execution, and routing-evidence endpoints remain during migration. They read from or compile into contracts where possible and return deprecation metadata.

The compiler lives behind a narrow interface:

```text
compile(contract, infrastructure, organization_policy)
  -> CompiledRoutingPolicy
```

The deterministic engine consumes only the compiled policy. The dashboard never duplicates compilation logic.

## Data and privacy

Headroom does not need prompt or response text to build the initial moat. The evidence model stores:

- prompt and repository fingerprints;
- bounded structural features;
- normalized task and client labels;
- contract and policy versions;
- model and deployment identities;
- cost, token, latency, retry, and fallback measures;
- quality and acceptance outcomes.

Workspace and repository identities remain hashed. Customers control retention and export. Enterprise deployments may keep evidence in their own environment.

## Commercial packaging

### Local

- local contracts and deterministic routing;
- starter templates;
- route receipts;
- local simulation;
- basic routing presets.

### Team

- shared contracts and policy history;
- historical replay and shadow evidence;
- canary rollout and rollback;
- CI and pull-request outcome integrations;
- quality-safe savings reports;
- alerts and team role templates.

### Enterprise

- signed policy bundles;
- SSO, RBAC, and approval workflows;
- residency and data-classification enforcement;
- central fleet management;
- custom evaluators and SLA routing;
- audit exports and private evidence storage;
- support for internal and fine-tuned models.

Team pricing should align with managed agent seats or active developers plus an included routing volume. Enterprise pricing should combine platform fee, governed usage, and support. Headroom should not depend on reselling provider tokens.

## Product moat

Headroom will accumulate privacy-safe evidence that links coding-agent workload context to routing decisions and engineering outcomes. The useful unit is not a generic prompt score. It is a contract-specific record of whether a model completed implementation, passed tests, survived review, avoided retry, and met cost and latency limits.

The defensible assets are:

- contract and task-specific quality evidence;
- provider-neutral decision receipts;
- safe abstention and promotion policy;
- coding-agent and harness integrations;
- outcome feedback from CI and review workflows;
- customer-owned policy and evidence history.

The open-source product creates adoption through local routing and receipts. Team and enterprise products monetize shared evidence, controlled rollout, governance, and integrations.

## Migration sequence

### Phase 1: Correctness and clarity

- fix mobile reflow and tab accessibility;
- label the two current routing layers and their precedence;
- make preview accept draft configuration;
- explain current policy and timeout behavior;
- separate model and deployment decisions in receipts.

### Phase 2: Contract foundation

- add the contract domain model and compiler;
- generate legacy contracts from roles and bindings;
- introduce versioning and lifecycle state;
- preserve existing engine behavior through compiled policy.

### Phase 3: Routing Studio

- ship Contracts and Simulator;
- add objective templates and reliability budgets;
- expose candidate rejection and policy diffs;
- add historical receipt replay.

### Phase 4: Evidence rollout

- ship Rollouts and Evidence;
- connect shadow, canary, promotion, pause, and rollback;
- make quality-safe savings the primary metric;
- add CI and pull-request outcome ingestion.

### Phase 5: Adaptive recommendations

- train contract-aware confidence and outcome models;
- recommend candidate objectives and thresholds;
- keep promotion operator-controlled by default;
- allow enterprise customers to opt into bounded automatic promotion.

## Testing strategy

### Contract and compiler tests

- schema validation and version migration;
- deterministic compilation;
- legacy role/binding equivalence;
- organization policy narrowing;
- invalid reliability budget rejection;
- immutable version and lifecycle transitions.

### Router tests

- hard constraints exclude candidates before ranking;
- blocked evidence cannot inherit a permissive global policy;
- objectives use total estimated cost and measured quality;
- exact assignment cannot widen to unrelated models;
- deployment selection cannot change model identity;
- stream fallback never occurs after visible output;
- receipts remain stable for applied, retained, rejected, and failed decisions.

### Simulation and rollout tests

- draft preview uses the draft version;
- live and draft diffs identify route and policy changes;
- historical replay does not invoke providers;
- canary assignment remains stable by request ID;
- promotion gates reject insufficient or unsafe evidence;
- rollback restores the previous immutable active version.

### Dashboard tests

- keyboard-complete workspace navigation;
- WCAG AA contrast and focus checks;
- 390, 768, 1024, and desktop reflow coverage;
- loading, stale, empty, conflict, and error states;
- screen-reader labels for objectives, evidence, and decision steps;
- screenshot regression coverage for Contracts, Simulator, Rollouts, and Evidence.

### End-to-end quality gates

- zero unsafe downgrade on the routing benchmark;
- no promotion when a populated segment violates its quality floor;
- deterministic receipt equality for fixed inputs and health snapshot;
- full migration equivalence for existing production role configurations;
- bounded worst-case execution time under retries and fallbacks.

## Success metrics

- quality-safe savings by contract;
- unsafe downgrade rate;
- accepted-task rate by routed model pair;
- fallback and retry rate;
- p90 time to first token and total task latency;
- percentage of decisions with complete receipts;
- time from draft policy to safe promotion;
- percentage of traffic covered by sufficient evidence;
- manual override and rollback rate.

## Acceptance criteria

1. A new user can create a coding-agent workload contract from a template, simulate it, and understand the selected route without reading backend documentation.
2. Existing role and binding configurations preserve their routing behavior after contract migration.
3. A draft preview evaluates the visible draft and labels it as draft.
4. The optimizer cannot select a candidate rejected by capability, transport, provider, account, residency, data, budget, or risk policy.
5. The product separates measured answer quality from deployment reliability.
6. The reliability budget exposes and enforces the maximum request duration and fallback cost.
7. Promotion requires contract-specific evidence and supports immediate rollback.
8. Every live and preview decision produces the same receipt schema.
9. The Routing Studio works at 390 pixels without horizontal page scrolling or off-canvas content.
10. Quality-safe savings replaces raw routed savings as the main commercial outcome.

