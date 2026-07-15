# Orchestration Routing and Roles Dashboard Refresh Design

## Problem

The Orchestrator dashboard already exposes routing, provider control, and role
binding surfaces, but the current implementation mixes several product layers
and has functional gaps:

- the Models tab references an undefined search state, so the tab is broken as
  soon as it renders;
- the Roles tab only supports a simple default model assignment even though the
  backend supports roles, bindings, selectors, required capabilities, equivalent
  deployments, and fallback chains;
- the Routing tab exposes valid backend policy values, but the UI needs clearer
  operator copy and a deterministic preview flow that matches the routing
  service contract;
- the Activity and provider-management panes need to remain accurate, read-only,
  and consistent with the same routing data model.

The goal is to make the dashboard best-in-class for operator correctness without
changing the existing six-tab structure.

## Goals

1. Keep the existing tabs: Providers, Models, Harnesses, Roles, Routing, and
   Activity.
2. Make every tab functional and internally consistent with the orchestration
   backend.
3. Preserve a simple “role → default model” path for common work while exposing
   advanced bindings only where needed.
4. Ensure the routing controls and preview use the same concepts as the backend
   route engine: mode, policy, retries, timeout, deployment cooldown, role,
   binding, selectors, required capabilities, fallback chain, and equivalent
   deployments.
5. Improve empty, loading, unavailable, and error states so the dashboard
   remains trustworthy when data is partial.

## Non-goals

- No navigation redesign.
- No backend API expansion.
- No new routing algorithm.
- No hidden automatic model reassignment.
- No change to the fundamental meaning of strict versus relaxed enforcement.

## Approved UX model

### Providers

Providers remain the operational account-management tab. It owns account
creation, credential storage, connection tests, model refresh, and credential
removal. The tab should keep the current action set, but loading and error
states must be explicit and button states must reflect in-flight actions.

### Models

Models become a discovery and verification tab. It should support search,
capability filtering, and clear availability/status presentation. The tab
should explain why a model is unavailable, deprecated, or not executable. The
search box must work and must not reference undefined state.

### Harnesses

Harnesses remain compatibility-only. They should present the transport posture
for each harness, but not imply model compatibility or change routing behavior.
The tab should continue to show whether the harness manifest is available and
how each harness relates to routing.

### Roles

Roles should use progressive disclosure:

- the main list shows the simple, common case: role name, description, and its
  locked default model;
- each role can reveal an advanced binding editor for selector-based overrides
  and policy metadata;
- advanced binding editing must support the fields already present in the
  backend contract: binding id, selectors, required capabilities, fallback
  chain, equivalent deployments, enabled state, and model assignment;
- the UI should treat bindings as the source of truth for deterministic routing,
  while the simple role-to-model control remains the quickest way to assign the
  default binding.

This is the key product correction: the dashboard should not force operators
into a single giant form, but it also should not hide the actual routing
primitives the backend enforces.

### Routing

Routing remains the global policy and preview tab. It should own:

- enforcement mode;
- routing policy;
- retries per model;
- timeout;
- deployment cooldown;
- deterministic route preview for a selected role.

The preview must show the selected role, assigned provider/model, reason,
fallback status, required capabilities, policy constraints, and any candidate
evidence the API returns. If the preview fails, the error should be explicit and
the last successful preview should not be silently overwritten.

### Activity

Activity remains a read-only execution history. It should summarize request id,
requested role, assigned model, actual model, provider, account, latency,
retries, fallback, routing reason, and result. The table should continue to
support search-driven filtering.

## Data flow

1. The dashboard loads orchestration config, provider accounts, models,
   executions, and harness compatibility.
2. Search text filters each tab’s visible data, but tab logic stays independent.
3. The Roles tab writes role assignments and advanced binding updates back
   through the orchestration config endpoint.
4. The Routing tab updates global routing settings and sends preview requests
   using the selected role.
5. The Activity tab renders execution records without allowing edits.

## Error handling

- A missing or partial API response should show a tab-level empty or
  unavailable state instead of rendering broken controls.
- A failed preview should retain the last known good preview until the operator
  explicitly retries.
- Mutating actions should disable their controls while in flight and should
  report failures inline.
- Unknown or unavailable backend values should render as safe fallback copy
  rather than crashing the component.

## Accessibility and interaction requirements

- Tabs must remain keyboard accessible and announce the active tab state.
- Form controls must keep visible labels.
- Buttons used as tab triggers or toggle groups must expose clear active/inactive
  state.
- Status copy must not rely on color alone.
- The layout must remain readable at the current dark-theme density on desktop
  and smaller laptop widths.

## Testing strategy

1. Add targeted unit or component coverage for the Models tab search state so
   the undefined variable bug cannot regress.
2. Add dashboard tests for the Roles tab’s default assignment path and the
   advanced binding editor flow.
3. Add routing preview coverage for the selected-role preview path and the
   error/empty-state presentation.
4. Add a regression check for the activity table and provider actions so the
   existing tabs still work after the refactor.
5. Run the dashboard test slice that exercises the Orchestrator and
   OrchestrationStudio surfaces, then run the broader dashboard lint/build pass.

## Acceptance criteria

- All six tabs render without runtime errors.
- The Models tab search works.
- Roles support both simple assignment and advanced routing metadata.
- Routing controls reflect the backend’s valid policy values and preview a
  deterministic assignment for a selected role.
- Activity and provider management continue to function.
- The dashboard looks and behaves like one coherent operator surface rather than
  a collection of disconnected controls.
