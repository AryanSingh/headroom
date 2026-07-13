# Universal Orchestration Implementation Plan

## Product boundary

Headroom will be a harness-neutral control plane for approved AI engineering
workloads. It will not replace an IDE or emulate every coding harness. Native
adapters preserve harness-specific tool loops; the control plane owns policy,
context handling, routing, execution evidence, and bounded handoffs.

## Delivery principles

- Enforce deterministic policy before introducing adaptive selection.
- Treat provider credentials, entitlements, data handling, and protocol
  semantics as provider-specific constraints.
- Exchange cross-harness work through explicit artifacts and verification
  evidence, never opaque conversations or hidden reasoning.
- Default to explainable routing and no silent capability downgrade.
- Gate every adaptive change behind offline evaluation, shadow mode, and
  rollback.

## Phase 0 — Routing foundation

### Status: implemented

Deliver a versioned routing decision receipt and hard eligibility constraints.

Completed in this branch:

- `RoutingRequest` accepts provider allow-lists, region allow-lists, data
  classification, token estimates, and an estimated-cost ceiling.
- The deterministic engine rejects non-compliant deployments before selection.
- `RoutingDecision` persists the evaluated constraints as `policy_constraints`
  and exposes `receipt_version` for API compatibility.
- The orchestration route-preview API accepts and returns these fields.

Implemented acceptance criteria:

- Layered organization/project defaults narrow constraints monotonically and
  cannot be broadened by a caller or lower-precedence configuration layer.
- Execution telemetry retains policy version and evaluated constraints.
- The supported-deployment capability manifest distinguishes `verified` from
  `advertised` capabilities; it never infers support from a model name.

## Phase 1 — Routing Profiles MVP

### Status: implemented foundation

Create a user-facing profile layer for `planner`, `implementer`, `reviewer`,
and `fast-worker` roles.

1. Version role/profile definitions and resolve them into existing route
   bindings.
2. Add a CLI and dashboard route-preview surface that shows selected and
   rejected deployments, constraints, estimated cost, and fallback behavior.
3. Support only direct/BYOK and explicitly approved enterprise gateway
   accounts. Subscription telemetry informs availability; it must not be used
   to repurpose a provider subscription for another provider.
4. Ship shadow mode before automatic changes to a request's deployment.

Implemented:

- Versioned profiles resolve to existing role bindings and may only narrow
  provider/capability/cost constraints.
- Profile and capability inspection APIs expose the effective contract.
- `/v1/orchestration/route/shadow` compares a candidate route without a
  provider call, model output, side effect, or cost.

Exit criteria: an individual can apply a profile across Codex and Claude Code
while retaining each harness's normal UX, and see an exact routing receipt.

## Phase 2 — Evaluation and scheduling evidence

### Status: implemented foundation

1. Define a task taxonomy: planning, implementation, tests, review, research,
   documentation, long-context analysis, and security review.
2. Persist privacy-safe outcome signals: verification result, retry/revert,
   review disposition, latency, cost, and explicit developer feedback.
3. Build replayable offline evaluations for candidate routes.
4. Rank only among policy-eligible models. Begin in recommendation/shadow mode
   and require a measurable quality/cost improvement to graduate a route.

Implemented:

- A closed task taxonomy is attached to route/execution records.
- Append-only outcome telemetry accepts only bounded verification, review,
  retry, revert, and rating signals—not prompt or repository content.
- Replayable routing evaluations compare decision metadata only and guarantee
  zero provider calls.

Exit criteria: every automated routing policy has an evaluation dataset,
quality threshold, and rollback rule.

## Phase 3 — Bounded cross-harness workflows

### Status: implemented foundation

1. Define a versioned task-artifact contract: task spec, repository/worktree
   reference, allowed tools, patch, test output, review finding, and provenance.
2. Add adapter capabilities for Codex, Claude Code, and OpenCode; classify each
   feature as native, configured, gateway-mediated, experimental, or unsupported.
3. Extend the existing durable DAG runner with human approval and verification
   gates for side-effecting work.
4. Permit automatic fallback only before an action begins, unless an adapter
   supplies idempotency and compensation semantics.

Implemented:

- Versioned task artifacts describe repository/worktree references, allowed
  tools, patch/test/review evidence references, and provenance.
- Human approval and verification gates pause durable workflow execution rather
  than permitting an unreviewed side effect or result to advance.
- A public harness compatibility manifest classifies Codex, Claude Code, and
  OpenCode support and explicitly rules out hidden-session sharing.

Exit criteria: an explicitly approved planner → implementer → reviewer workflow
can resume safely with full evidence and without sharing hidden harness state.

## Phase 4 — Enterprise control plane

### Status: implemented foundation

1. Compile organization, project, and workspace policies into signed bundles.
2. Integrate KMS/Vault and customer secret managers; local encrypted storage is
   appropriate only for single-user development.
3. Enforce data classification, residency, provider/model allow-lists, egress,
   budgets, retention, and tool/action permissions at the gateway.
4. Make the decision receipt an immutable audit record linked to execution
   telemetry and spend attribution.
5. Validate SSO/SCIM/RBAC and audit/export paths through deployment tests.

Implemented:

- The effective orchestration policy compiles to a canonical, versioned,
  prompt-free policy bundle with a stable hash. Customer-controlled Ed25519
  keys can sign and verify that bundle.
- When `CUTCTX_ORCHESTRATION_AUDIT_KEY` is configured, executed routing
  receipts are persisted in an HMAC-linked append-only audit chain. Operators
  can verify integrity and export JSONL through authenticated APIs.
- The orchestration service deliberately retains the existing encrypted local
  credential store as a development fallback. An external secret-resolver
  protocol now allows a Vault/KMS/cloud-secret-manager adapter to resolve
  explicit references without enumerating its namespace or copying secrets
  into local orchestration state.

Exit criteria: a platform team can prove why an execution was permitted, which
deployment ran it, what it cost, and which policy version governed it.

## Phase 5 — Adaptive scheduler and ecosystem

### Status: implemented recommendation foundation

1. Use health, quota headroom, observed latency, context fit, cost, task type,
   and verified outcome history to rank eligible deployments.
2. Add canary cohorts, per-profile quality guardrails, rollback, and drift
   alerts.
3. Publish an adapter SDK and a public compatibility matrix; tier integrations
   by support level rather than claiming universal semantic parity.
4. Add private/local inference deployment support through the same capability
   manifest and policy engine.

Implemented:

- The scheduler is strictly `recommendation_only`: it joins task-scoped,
  privacy-safe outcome signals to prior execution records and recommends only
  deployments with enough verified evidence to clear configured quality
  thresholds.
- Candidate deployment resolution uses the same shadow route path and therefore
  cannot bypass policy, capability, residency, or budget constraints.
- Canary assignment is deterministic and defaults to zero sampling. It is a
  cohort/evaluation signal only; it does not change an execution route.
- Drift detection compares adjacent verified-outcome windows and emits an
  advisory-only quality-regression signal with an evidence minimum. It cannot
  trigger a route mutation or rollback by itself.

Deferred to a subsequent productionization milestone:

- Automated route application, drift-alert delivery, private-inference fleet
  adapters, and marketplace/SDK distribution. These require live operational
  ownership and design-partner evidence beyond a repository-local change.

Exit criteria: Headroom continuously improves routing within explicit policy
and quality limits, while every recommendation remains explainable.

## Non-goals

- Building a replacement editor or universal agent UI.
- Silent cross-provider substitution for provider-native harness workflows.
- Treating OpenAI-compatible wire format as proof of tool/reasoning equivalence.
- Unbounded autonomous multi-agent execution.
