# Guided Safe Savings Mode Design

## Goal

Turn the existing conservative model-routing preset into a commercially clear,
operator-facing Safe Savings experience without changing any routing decision,
provider credential, request payload, or transport-safety rule.

The first release adds a normalized explanation model, a read-only CLI summary,
and a dashboard surface. It also exposes the existing Off control as an
explicit rollback. The feature is an explanation and configuration experience
over the current router, not a new router.

## User outcomes

An operator can answer these questions without reading raw traces:

1. Is model routing off, balanced, aggressive, or custom?
2. Which exact source-to-target routes are eligible under the active preset?
3. Did a recent request route, and if not, why was it retained?
4. Which confidence, capability, or transport signal affected the decision?
5. How can routing be returned to Off without editing files or environment
   variables manually?

## Scope

### Included

- A provider-neutral Safe Savings status representation derived from existing
  router configuration and routing traces.
- Human-readable explanations for every terminal optimization-routing reason
  currently emitted by the router.
- Exact eligible route pairs, including low and optional medium targets.
- Current mode, preset, enabled state, transport-safe targets, and route count.
- Recent decision summaries using already-persisted routing metadata.
- A read-only CLI status command using the same backend representation.
- A dashboard Safe Savings panel in the existing Orchestrator product area.
- An explicit Off action implemented through the existing authenticated
  orchestrator configuration control.
- A feature flag that hides the new product surface by default while leaving
  all routing behavior unchanged.

### Excluded

- New complexity heuristics or scorer behavior.
- Provider-family wildcards.
- Automatic cross-provider selection.
- New fallback behavior.
- Changes to capability, account, credential, or transport proof.
- Automatic contract promotion.
- New provider calls, shadow replays, or prompt/response telemetry.
- A second source of truth for routing configuration.

## Architecture

### Shared explanation model

A new backend module owns the stable presentation model. It accepts current
router/config state and an optional existing routing trace or routing summary,
then returns JSON-safe data:

- `mode`
- `enabled`
- `preset`
- `route_count`
- `routes`
- `transport_safe_targets`
- `decision`
- `rollback_available`

Each route contains only exact configured identifiers:

- `source_model`
- `low_target_model`
- optional `medium_target_model`
- declared low/medium capabilities
- whether each target is transport-safe for restricted transports

The optional decision contains:

- requested, effective, and candidate model
- applied state
- stable reason code
- human-readable title and explanation
- scorer, confidence, and non-sensitive signals
- required or missing capabilities
- transport proof fields already present in the trace

The explanation map is exhaustive for known terminal reason codes and has a
safe fallback for unknown future codes. Unknown reasons remain visible by code
and never crash the CLI or dashboard.

This module is presentation-only. It must not call `maybe_route`, mutate router
configuration, infer capabilities, perform provider calls, or write telemetry.

### API

Add an authenticated read-only orchestration endpoint that returns the shared
Safe Savings representation. It reads the live router and the existing recent
request/routing data already available to the proxy. Calling it must be
observational: repeated calls cannot change configuration, routing counters,
credentials, request logs, or canary assignment.

The existing authenticated configuration endpoint remains the only mutation
path. The dashboard Off action uses the existing `orchestrator_mode = "off"`
behavior rather than introducing a parallel toggle.

### CLI

Add a `cutctx routing status` read-only command. It queries the running proxy
and prints:

- current Safe Savings mode and preset;
- enabled/disabled state;
- exact eligible route pairs;
- transport-safe target posture;
- the most recent routing decision and explanation when available.

The command exits successfully when routing is Off and clearly says that the
requested model will be retained. Connection, authentication, and unsupported
server responses use existing CLI error conventions. The CLI does not mutate
configuration.

### Dashboard

Add a Safe Savings panel to the existing Orchestrator area. It contains:

- current mode and preset;
- route-pair table;
- most recent applied/retained decision;
- confidence/signals and missing-capability details when present;
- transport-safety posture;
- an Off action with explicit confirmation copy.

The panel must describe a retained request as protected/retained, not as a
failure. Status cannot rely on color alone. The Off action is the only mutation
in the first release; it reuses the existing API, disables while pending, and
refreshes authoritative state after success.

## Feature flag and compatibility

The new API representation may exist unconditionally because it is read-only.
The CLI command and dashboard panel are hidden unless the Safe Savings
experience flag is enabled. The flag controls discoverability only; it must
never enable model routing or alter a router config.

With the flag disabled:

- existing API request/response behavior remains compatible;
- existing dashboard layout and controls remain unchanged;
- no new provider, model, or credential work occurs;
- route decisions and request payloads are byte-for-byte equivalent.

With the flag enabled but routing Off, the product surface reports Off and does
not offer or imply an applied route.

## Error handling

- Missing router: return a valid Off representation.
- Missing preset: report Custom or Off using the existing normalization rules.
- Missing recent decision: render “No recent routing decision.”
- Unknown reason: retain the raw code and use neutral fallback copy.
- Partial legacy metadata: omit unavailable optional fields without inventing
  confidence, capabilities, targets, or transport proof.
- Failed Off action: preserve the last known display, show the error, and do
  not optimistically claim routing is disabled.

## Security and privacy

- The status representation contains no API keys, credential references,
  account secrets, prompt text, response text, or raw workspace identity.
- Existing admin authentication and RBAC protect the endpoint and Off action.
- The representation does not accept model, provider, account, mode, or policy
  overrides.
- Provider/account mismatch and unproven transport reasons remain visible but
  cannot be bypassed from this surface.

## TDD and BDD verification

Implementation follows strict red-green-refactor cycles.

### Backend behavior

**Given** a supported source route and an applied trace, **when** the status
representation is built, **then** it contains the exact source/target,
confidence/signals, and applied explanation.

**Given** a capability or transport-blocked trace, **when** the representation
is built, **then** it retains the requested model and exposes the stable block
reason and relevant missing capability or transport proof.

**Given** no live router or an Off router, **when** status is requested,
**then** it reports Off and rollback is unavailable.

Unit tests must cover every currently emitted terminal reason and the unknown
reason fallback. A mutation regression test snapshots router config and
metadata before and after representation construction.

### CLI behavior

**Given** routing is enabled, **when** an operator runs `cutctx routing status`,
**then** exact routes and the current decision are printed without making a
mutation request.

**Given** routing is Off, **when** status is requested, **then** the command
exits successfully and explains that the requested model is retained.

CLI tests must assert the request method/path, output, authentication error
handling, partial legacy payload behavior, and absence of mutation calls.

### Dashboard behavior

**Given** an applied decision, **when** the panel renders, **then** it shows the
source-to-target pair and applied explanation.

**Given** a blocked decision, **when** the panel renders, **then** it shows the
retained model and reason without presenting a bypass control.

**Given** the operator confirms Off, **when** the existing mutation succeeds,
**then** authoritative status is refreshed and the panel reports Off.

Component tests cover loading, Off, applied, blocked, unknown-reason, failed
mutation, keyboard access, and non-color status text.

### Regression gates

- Existing model-router, preset, routing-quality, orchestration, and
  compatibility-handler tests pass unchanged.
- Enabling the experience does not alter routing decisions for a fixed corpus.
- The status endpoint performs zero provider calls and zero state writes.
- Dashboard lint, component tests, and production build pass.
- CLI tests and relevant Python formatting/type checks pass.

## Delivery order

1. Backend presentation-model tests, then minimal implementation.
2. Authenticated status endpoint tests, then endpoint.
3. CLI tests, then `routing status`.
4. Dashboard component tests, then panel.
5. Feature-flag and Off-action tests, then integration.
6. Focused and broad regression verification.

## Success criteria

- Operators can understand current mode, eligible exact routes, and recent
  applied/retained decisions from both CLI and dashboard.
- Every known retention reason has stable, useful, non-sensitive copy.
- The Off action uses the existing authoritative configuration path.
- No route decision, credential boundary, capability gate, transport proof,
  provider call, or request payload changes as a consequence of viewing status.
- All TDD and regression gates pass.
