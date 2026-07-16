# Product Manager Audit: Model Routing and Orchestration

Date: 2026-07-15
Primary target: coding-agent teams and engineering leaders

## Executive assessment

Headroom has stronger safety and explainability primitives than a generic LLM gateway, but the product surface does not yet communicate or operationalize that advantage. The current experience is configuration-first, combines two routing systems under one vocabulary, and makes important policy behavior implicit.

The product should be repositioned as an evidence-backed control plane for coding agents and long-running AI work: define workload contracts, enforce hard safety constraints, route deterministically, measure outcomes, and promote policy changes through evidence.

## Existing capabilities

- Role and selector-based deterministic bindings.
- Required-capability checks and provider/account identity.
- Strict and relaxed enforcement modes.
- Configured fallback chains and equivalent deployments.
- Deployment cooldowns and retry budgets.
- Provider, region, data-classification, and budget constraints.
- Unified routing decision traces and execution receipts.
- Privacy-preserving shadow evidence and confidence abstention.
- Transport/harness compatibility checks.
- Cost-saving model optimization presets and complexity heuristics.

## Product gaps

### 1. No single routing mental model

Deterministic orchestration and optimization routing are both called routing. Operators cannot easily answer which layer wins, when a policy is ignored, or whether a route changed because of workload complexity, health, fallback, or a role binding.

### 2. Roles are under-modeled

Roles currently behave primarily as named model assignments. For coding-agent teams, a role should be a workload contract with capabilities, quality floor, latency/SLA target, budget, data policy, fallback posture, and evaluation criteria.

### 3. Preview is not a planning tool

The route preview is a single-role lookup. It does not preview unsaved drafts, model the request context, show all candidate rejections, compare policy versions, calculate worst-case latency/cost, or produce a shareable receipt.

### 4. Evidence is disconnected from deployment

Shadow quality/cost evidence exists, but the main workflow does not turn it into a clear draft → shadow → canary → promote lifecycle.

### 5. Policies are misleadingly named

“Highest quality” currently uses reliability metadata, “Cheapest” uses input price only, and “Balanced” is a fixed ranking formula. The UI does not explain these semantics or their strict/relaxed interaction.

### 6. Missing coding-agent workflow integrations

The product needs first-class repository, branch, pull request, CI, tool-loop, task-type, and developer-acceptance signals. These are the signals that make routing valuable for coding-agent teams and difficult for generic gateways to copy.

## User journey friction

1. User lands on infrastructure tabs before expressing a workload objective.
2. User creates a role without understanding capabilities, quality, cost, or SLA implications.
3. User sees two routing controls with overlapping labels.
4. User previews a route but may be previewing saved server state rather than the visible draft.
5. User has no safe simulation or policy-diff step before saving.
6. User sees savings evidence but not quality regression risk by role or repository.
7. User cannot easily explain a routing decision to a teammate or auditor.

## Onboarding issues

- No opinionated starter roles for common coding-agent tasks.
- No “connect a harness → choose a role → run a preview” guided path.
- No sample request scenarios when no roles exist.
- No recommended policy based on team priorities.
- No explicit explanation of what strict mode protects.

## Retention opportunities

- Weekly verified savings and quality report by role/repository.
- Regression alerts when a cheaper target falls below a quality floor.
- Canary recommendations based on evidence.
- Policy drift and provider-health notifications.
- Shareable routing receipts attached to CI runs and pull requests.
- Team role templates and reusable policy packs.

## Competitive comparison

LiteLLM emphasizes load balancing, retries, cooldowns, fallbacks, timeouts, and provider failover ([official routing docs](https://docs.litellm.ai/docs/routing)). OpenRouter emphasizes provider routing with order, fallback, data policy, ZDR, price/throughput/latency sorting, performance thresholds, and max price ([official provider routing docs](https://openrouter.ai/docs/guides/routing/provider-selection)).

Headroom should not compete primarily on generic gateway breadth. Its defensible position is policy-bounded, context-aware routing for agent workflows with privacy-safe outcome evidence and auditable receipts.

## Recommended north-star metrics

- Quality-safe savings: cost reduction while meeting each role’s quality floor.
- Unsafe downgrade rate: target zero for high-risk/tool-loop work.
- Route explainability rate: percentage of executions with a complete receipt.
- Policy iteration time: time from observed evidence to safe canary.
- Developer acceptance rate by role and target model.

## Commercialization recommendation

- Local/free: deterministic roles, receipts, presets, and basic local evidence.
- Team: shared role contracts, policy simulation, shadow evaluation, canaries, CI/Pull Request integrations, and quality-safe savings reporting.
- Enterprise: signed policy bundles, residency/data controls, SSO/RBAC, audit exports, centralized fleet management, custom evaluators, and SLA routing.

Sell verified cost reduction under an explicit quality and reliability envelope—not raw token savings.
