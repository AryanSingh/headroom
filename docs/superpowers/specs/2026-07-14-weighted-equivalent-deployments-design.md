# Weighted equivalent deployments

## Goal

Provide controlled, reproducible traffic allocation for safe same-model
deployments, closing the live canary/weighted-routing gap without permitting
cross-model, cross-provider, cross-harness, or cross-transport substitution.

## Scope and boundary

`RouteBinding` gains `equivalent_deployment_weights: dict[str, float]`. Keys
must identify deployments already listed in `equivalent_deployments` or the
binding primary. The primary is an allowed key so an operator can set, for
example, a 95/5 rollout between two accounts hosting the same model.

The existing config validator rejects non-finite, negative, unknown, and
different-model weighted targets. An empty map retains the current
health/reliability ranking exactly.

## Selection algorithm

1. Resolve the primary and explicit equivalents, validating their same-model
   identity as today.
2. Apply all current eligibility gates: configured account, cooldown,
   availability, deprecation, capability, residency, data classification, and
   budget.
3. If weights are configured and at least one eligible deployment has a
   positive weight, hash the stable request ID into the normalized weight
   interval and choose that deployment.
4. If the preferred weighted deployment is ineligible, redistribute only
   across the remaining eligible positive-weight deployments. Never route to a
   zero-weight deployment due solely to weights.
5. If every eligible deployment has zero/no configured weight, retain the
   existing reliability ranking rather than inventing traffic allocation.

The request ID is generated before selection when absent, so one routing
decision remains internally deterministic. A repeated explicit request ID
always maps to the same eligible weighted deployment.

## Safety

- Strict mode can use weighted equivalents because they are explicitly declared
  and preserve model identity; it still cannot use a different fallback model.
- Weights have no effect until policy, capability, transport, and cooldown
  checks pass.
- A cooled or otherwise ineligible deployment is reported in selection
  evidence and receives no traffic.
- Fallback remains retry/pre-first-byte only and is unchanged.

## Receipt and UI

Selection evidence reports `strategy: equivalent_weighted`, the chosen
deployment, normalized eligible weights, cohort hash fraction, and rejected
candidates. The existing Route preview will display the selection strategy and
eligible/rejected details using the evidence panel added in the prior feature.

The first implementation exposes weights through the serialized routing
configuration/API. The Studio keeps model assignment simple and displays the
resulting receipt; a dedicated bulk rollout editor is deferred until role
binding editing supports fallback/equivalent configuration.

## Tests

1. Invalid weights are rejected by configuration validation.
2. The same explicit request ID consistently picks the same weighted
   equivalent; a range of IDs covers both positive-weight targets.
3. A cooled weighted target receives no traffic and is present in rejected
   receipt evidence.
4. Strict mode remains unable to route to a different-model fallback.
