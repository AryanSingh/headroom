# Orchestration Dashboard Clarity and Live E2E Design

## Decision

Evolve the existing Cutctx dashboard instead of replacing its visual system.
Keep the current type, color, card, control, and icon language, but reorganize
the Orchestrator page around the operator's three jobs:

1. **Operate** controls live routing and shows the next useful action.
2. **Contracts** authors, simulates, and releases workload contracts.
3. **Configuration** manages providers, models, roles, policy, and activity.

The page must stop presenting routing status, provider policy, legacy failover,
contract authoring, and platform configuration as one uninterrupted stack.

## Problem

The current `/orchestrator` route exposes three product layers at once:

- live routing mode, evidence, savings, readiness, provider policy, and legacy
  provider controls;
- contract drafting, simulation, evidence, and rollout;
- provider accounts, credentials, models, harnesses, role bindings, routing
  policy, and execution activity.

The long page makes the starting point unclear and pushes contract work below
diagnostic panels. On narrow screens, the fixed dashboard chrome interrupts the
vertical flow. Several browser tests exercise mocked API responses, but no
browser suite proves that every exposed mutation reaches a live proxy and
produces the expected backend state.

## Goals

- Give the route one primary workspace selector with **Operate**, **Contracts**,
  and **Configuration**.
- Make Operate the default workspace.
- Show live routing mode, status, savings, and one recommended next action near
  the top of Operate.
- Move detailed readiness, policy, provider failover, and diagnostics behind a
  secondary disclosure in Operate.
- Keep the complete contract lifecycle available in Contracts.
- Keep provider, model, harness, role, routing-policy, and activity tools
  available in Configuration.
- Preserve backend API contracts and orchestration semantics.
- Add browser-to-live-proxy tests for every exposed mutation.
- Retain mocked browser tests for deterministic race, timeout, and failure
  scenarios that a live fixture cannot produce reliably.

## Non-goals

- No routing algorithm changes.
- No provider calls to paid external services in tests.
- No new dashboard framework or visual-design dependency.
- No removal of advanced orchestration controls.
- No claim that a provider connection succeeds unless a local deterministic
  provider fixture handles the request.
- No broad redesign of dashboard routes outside `/orchestrator`.

## Information Architecture

### Page header

The route header identifies **Orchestrator**, shows proxy health, and keeps the
existing global search and theme controls. Directly below it, a workspace
tablist exposes Operate, Contracts, and Configuration. Tabs support arrow keys,
Home, End, visible focus, and a single tab stop.

### Operate

Operate contains a compact command section:

- Off, Auto, and Aggressive routing modes;
- current live or pending state;
- routed cost and token savings;
- routing evidence summary;
- one recommended action derived from current state.

The recommended action follows deterministic rules:

- unavailable configuration API: explain that controls require a compatible
  proxy build;
- routing off with no configured roles: link to Configuration → Roles;
- routing off with configured roles: recommend Auto;
- evidence collecting: recommend continued shadow evidence collection;
- evidence ready: link to Contracts → Rollouts;
- unhealthy provider: link to Configuration → Providers;
- otherwise: state that routing is operational.

A collapsed **Diagnostics and compatibility** section contains routing
readiness, provider policy, legacy provider failover controls, and Safe Savings
details. Errors stay within the section that owns them. A diagnostic API
failure must not dominate or disable the command section.

### Contracts

Contracts renders the existing Routing Studio as the workspace body. Its inner
Contracts, Simulator, Rollouts, and Evidence tabs remain because they describe
one lifecycle. The workspace adds a short step indicator:

`Draft → Simulate → Shadow → Canary → Active`

The lifecycle keeps immutable draft save, deterministic no-call simulation,
evidence gates, start shadow, promote to canary, promote to active, pause, and
rollback. Disabled actions must explain their gate in visible copy.

### Configuration

Configuration renders the existing Orchestration Studio. Its Providers, Models,
Harnesses, Roles, Routing, and Activity tabs remain. The workspace intro tells
operators that these controls change infrastructure and policy, not the current
contract draft.

The configuration save button reports dirty, saving, saved, and failed states.
Local edits must not imply persistence until the live proxy acknowledges the
PUT request.

## Responsive Behavior

- At widths below 700px, workspace tabs remain horizontally reachable without
  clipping the active item.
- The mobile header must occupy normal document flow while the Orchestrator
  workspace is open; it must not cover controls or tables.
- Cards collapse to one column.
- Wide tables use an explicitly labelled horizontal scroll region.
- Primary actions remain at least 44 by 44 CSS pixels.
- No document-level horizontal overflow is allowed at 390px.

## Accessibility

- Workspace and nested tabs use the ARIA tab pattern with `aria-controls`,
  `aria-labelledby`, arrow-key navigation, Home, End, and roving `tabIndex`.
- Status changes use `role="status"`; actionable failures use `role="alert"`.
- Color never carries the only indication of pending, warning, success, or
  disabled state.
- Disclosure controls expose `aria-expanded` and an accessible name.
- Focus remains visible for keyboard users.
- Motion respects `prefers-reduced-motion`.
- The implementation must pass the existing JSX accessibility lint rules and
  automated browser checks for high-impact accessible-name and keyboard
  behavior.

## Live E2E Definition

A test qualifies as live proxy E2E only when:

1. Playwright opens the built or Vite-served dashboard.
2. The dashboard sends requests to a real FastAPI proxy process created from
   the repository's production app factory.
3. The test authenticates through the normal admin-key path.
4. Mutations use production HTTP routes without Playwright route fulfillment.
5. The assertion reads the resulting state through a production API or a
   dashboard reload.
6. Each test receives isolated temporary storage and deterministic local
   provider fixtures.

Playwright route mocks may cover timeouts, stale responses, malformed
acknowledgements, and forced server failures. They do not satisfy the live E2E
requirement.

## Control Coverage Matrix

| Workspace | Control | Required live evidence |
|---|---|---|
| Operate | Off / Auto / Aggressive | POST `/config/flags`, refresh stats, reload UI, mode persists |
| Operate | Safe Savings off | confirmation, live flag mutation, live status reads off |
| Operate | Legacy provider enable / disable | production provider action route changes live provider status |
| Contracts | Save immutable draft | persisted contract survives reload |
| Contracts | Run draft simulation | production simulation response renders and reports zero provider calls |
| Contracts | Start shadow | contract state becomes `shadow` |
| Contracts | Promote to canary | ready evidence fixture allows transition to `canary` |
| Contracts | Promote to active | canary contract transitions to `active` |
| Contracts | Pause rollout | eligible contract transitions to `paused` |
| Contracts | Roll back | active contract transitions through production rollback behavior |
| Configuration | Add provider account and credential | account and credential metadata survive reload without exposing secret |
| Configuration | Test provider connection | local deterministic provider returns healthy result |
| Configuration | Refresh models | production refresh route updates registry view |
| Configuration | Remove credential | confirmation, deletion, reload shows credential missing |
| Configuration | Save roles and default assignment | config GET returns the saved role and binding |
| Configuration | Add, edit, enable, disable, delete selector binding | config GET matches every change after save |
| Configuration | Save enforcement and routing policy settings | config GET matches mode, policy, retry, timeout, and cooldown |
| Configuration | Route preview | production route endpoint returns the selected deployment and evidence |
| Configuration | Search and tab navigation | browser-visible filtering and keyboard behavior use live-loaded data |

## Error Coverage

Every mutation family needs one deterministic browser test for:

- pending state disables duplicate submission;
- server rejection appears beside the owning control;
- local optimistic state does not claim persistence after rejection;
- retry or reload recovers from the failure.

The mode selector keeps its existing stale-response and acknowledgement tests.
Contract save keeps revision-conflict coverage. Credential deletion and Safe
Savings keep explicit confirmation coverage.

## Test Architecture

Add a dedicated live Playwright project and fixture:

- a Python launcher starts an isolated proxy on an ephemeral port with a
  temporary configuration and orchestration store;
- a deterministic local provider stub supports connection tests and model
  discovery without external traffic;
- Vite proxies dashboard API requests to the isolated proxy, or the test injects
  the proxy base URL through the dashboard's supported configuration path;
- test helpers seed contracts and evidence through production APIs;
- live tests carry a `@live-proxy` tag and never call `page.route()` for
  production endpoints.

Keep `dashboard/e2e/orchestrator.spec.js` for mocked concurrency and UI-state
tests. Add a separate `dashboard/e2e/orchestrator-live.spec.js` so reviewers can
identify the stronger boundary at a glance.

## File Boundaries

- `dashboard/src/pages/Orchestrator.jsx`: page data, workspace selection, live
  mode actions, and recommended-action derivation.
- `dashboard/src/components/OrchestratorWorkspaceTabs.jsx`: accessible primary
  workspace navigation.
- `dashboard/src/components/OrchestratorOperate.jsx`: command section and
  diagnostics disclosure.
- `dashboard/src/components/OrchestrationStudio.jsx`: configuration sub-tabs and
  mutations.
- `dashboard/src/components/routing-studio/RoutingStudio.jsx`: contract
  lifecycle.
- `dashboard/src/index.css`: responsive workspace layout using existing tokens.
- `dashboard/e2e/fixtures/live-proxy.js`: process lifecycle and isolated test
  fixture.
- `dashboard/e2e/orchestrator-live.spec.js`: browser-to-proxy control matrix.
- `tests/fixtures/orchestration_e2e_server.py`: production app plus local
  provider fixture launcher.

## Verification

Completion requires all of the following:

- control matrix has a passing live test for every row;
- mocked orchestration browser tests pass;
- focused orchestration backend tests pass without orchestration-related skips;
- dashboard unit tests pass;
- ESLint passes with zero warnings;
- production dashboard build succeeds;
- desktop and 390px screenshots show Operate, Contracts, and Configuration;
- keyboard traversal works for both primary and nested tabs;
- 390px document overflow is at most one pixel;
- no fixed dashboard chrome covers the active mobile workspace;
- no browser console errors occur in successful live flows.

## Trade-offs

The three-workspace structure adds one navigation step before advanced
configuration. That step protects the daily routing and contract paths from the
configuration surface's density. The live fixture adds test startup time, but
it replaces indirect mocked confidence with evidence across the actual HTTP,
authentication, persistence, and reload boundaries.
