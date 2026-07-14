# Deployment cooldown and route explanations

## Goal

Close the remaining operational-routing gaps: isolate a deployment after a
classified provider failure, and make the decision receipt understandable in
the Orchestrator without changing cross-harness or cross-transport safety.

## Decision

Add a deployment-scoped cooldown held in the dynamic model registry. A
cooldown is keyed by the full deployment key (`provider:account:model`), not
the provider or the model name. It is applied only after the configured retry
budget for the current deployment has been exhausted and a normalized failure
trigger is one of `timeout`, `rate_limit`, `provider_outage`, `auth_failure`,
or `quota_exhausted`.

The cooldown is an availability overlay, not a permanent health mutation:

- Its expiry is recorded as a wall-clock epoch in the deployment metadata so
  the existing registry cache preserves it across process restarts.
- An expired value is removed before eligibility evaluation.
- The deployment remains registered, capability-bearing, and eligible again
  when the cooldown expires.
- A manual healthy account probe clears the cooldown for that account's
  deployments; a failed probe leaves the cooldown in place.

`RoutingSettings` gains `deployment_cooldown_seconds`, defaulting to 30 and
bounded between 1 and 3600 seconds. Existing configurations deserialize to the
safe default.

## Routing behavior

The engine asks the registry whether each candidate is cooling down before
selecting it. It reports `cooling_down` as the rejection reason in the existing
selection evidence.

- Strict mode remains strict: it may select an explicitly declared,
  same-model equivalent deployment, but never a different fallback model.
- Relaxed mode can follow its already-configured fallback chain only after
  eligible equivalents are exhausted.
- Provider/model/harness/transport compatibility checks remain unchanged and
  run independently of cooldown state.
- Streaming can only fall back before its first visible byte; a post-byte
  failure records the cooldown but terminates the stream instead of switching
  providers.

The executor records the cooldown only after retries for the same deployment
are exhausted, immediately before attempting configured fallback. This retains
the existing retry contract while preventing subsequent requests from being
routed back to a known-failed deployment.

## Operator experience

The Route preview retains the selected deployment and reason, then renders:

- a score table for eligible same-model equivalents;
- rejected candidates with their exact reason;
- an explicit empty state when no scoring evidence exists.

The view is diagnostic only. It does not issue provider calls or mutate route
configuration. A `cooling_down` reason lets an operator distinguish a temporary
deployment isolation from a capability or policy rejection.

## Interfaces

- `DynamicModelRegistry.cool_down(deployment_key, duration_seconds, now=None)`
  writes `cooldown_until_epoch` to metadata.
- `DynamicModelRegistry.cooldown_remaining_seconds(deployment_key, now=None)`
  returns a positive integer-ish remaining duration or `None`, clearing expired
  values atomically.
- `DeterministicRoutingEngine` treats a positive remaining value as
  `cooling_down` during eligibility checks.
- `OrchestrationService` invokes `cool_down` after a retry budget is exhausted
  for a configured cooldown trigger.

## Test strategy

Test first, in this order:

1. Registry cooldown is account/deployment scoped, survives a registry reload,
   and expires deterministically with an injected time.
2. A cooling primary selects its declared same-model equivalent in strict mode;
   receipt evidence names `cooling_down`.
3. Relaxed execution applies cooldown after retry exhaustion and falls back;
   a subsequent route avoids the cooled deployment.
4. A streaming post-first-byte failure records cooldown but does not switch
   providers.
5. Browser tests show candidate scores and rejection reasons in route preview.

## Non-goals

- Weighted traffic splitting across different models.
- Automatic cross-provider or cross-harness adaptation.
- Mid-stream provider switching.
- Changing a model's durable health score from a transient request failure.
