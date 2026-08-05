---
id: CH-05
kind: chapter
title: Dashboard UI Engineering and Audit
purpose: Verify dashboard journeys, state handling, accessibility, authorization presentation, and resilient client behavior.
audience: [Frontend engineers, designers, QA, accessibility and product leads]
scope: Critical journeys, loading/empty/error/unauthorized states, responsive behavior, accessibility, and client-server contracts.
applicability: Web dashboards, admin portals, and operational consoles.
owners: [Frontend owner, design owner, accessibility owner]
inputs: [journey map, route inventory, design states, API contracts, supported viewport matrix]
outputs: [state matrix, accessibility evidence, UI findings, release decision]
dependencies: [W3C-WCAG-2.2, NIST-SSDF-1.1]
standards: [W3C-WCAG-2.2, NIST-SSDF-1.1]
---

# Dashboard UI Engineering and Audit

## Purpose, audience, scope, and applicability

Audit the dashboard as a system of decisions, not a set of attractive screens.
Every critical journey needs an understandable loading, empty, error, stale,
unauthorized, and success state. Verify what the user can see, do, recover, and
export at realistic viewport and permission boundaries.

## Concepts and engineering principles

The UI must not invent authorization from hidden controls. Server authorization
remains authoritative, while the interface explains denied or unavailable
actions without leaking protected data. Semantic roles, names, focus order, and
keyboard operation are part of the interface contract. A visual baseline detects
change; it does not establish correctness without state and accessibility tests.

## Roles and accountability

Frontend owners maintain state contracts and component behavior. Design owners
approve intent and error-copy clarity. Accessibility owners review semantic and
assistive-technology behavior. API owners confirm error and permission contracts.

## Prerequisites and required inputs

Gather priority journeys, roles, feature flags, API error shapes, state designs,
analytics definitions, supported browsers/viewports, and deterministic fixtures
for success and failure states.

## Standard operating procedure

1. Define priority journeys and enumerate each state transition.
2. Test role-based routes with legitimate, unauthorized, expired, and absent sessions.
3. Verify loading, empty, error, retry, stale-data, and offline behavior.
4. Test keyboard traversal, visible focus, names/roles, contrast, zoom, and
   responsive layout with representative content lengths.
5. Intercept APIs in deterministic tests to force error and delayed responses.
6. Compare visual baselines only after semantic/state assertions pass.

## Worked example

[Atlas Revenue dashboard state matrix](../examples/dashboard-states/README.md)
tests delayed data, no data, expired session, and provider error without calling
a live service.

## Automation examples

Use role/label/test-id locators, not fragile DOM position. Run a state matrix
per critical route and retain screenshots, traces, accessibility output, and
network fixtures for a release candidate.

## Audit prompts

Use [Opus](../prompts/opus/ch05-ui-journey.md),
[Sonnet](../prompts/sonnet/ch05-state-review.md), and
[Haiku](../prompts/haiku/ch05-ui-inventory.md) for journey synthesis, focused
state evidence review, and inventory normalization.

## Workflow checklist

Run [CL-UI-01](../checklists/dashboard-ui.md) before releasing a changed
journey, permission model, or component library.

## Evidence requirements and retention guidance

Retain fixture versions, browser/viewport, route and role, test trace,
screenshot, accessibility result, API mock, source revision, and reviewer note.
Do not retain customer content in visual baselines.

## Example findings with severity and remediation

**Important — UI-ATLAS-01.** An expired session rendered the previous account’s
revenue total while the refresh request failed. Remediation: clear sensitive
cached data on auth transition, render a signed-out state, and add a regression test.

## KPIs and domain scorecard

The [dashboard KPI catalog](../scorecards/dashboard-kpis.md) tracks critical
state coverage, accessibility blocker age, error recovery success, and visual
baseline review latency.

## Common failure patterns and diagnostic guidance

- Empty and error states share copy but require different next actions.
- Hidden buttons create an impression of authorization while APIs remain exposed.
- A mocked success path hides slow/error behavior.
- Visual tests cover desktop only and miss narrow viewport overflow.

## Exit criteria

Exit when every critical journey has deterministic state evidence, accessibility
blockers are closed, protected data is cleared on auth boundaries, and visual
changes have an approved semantic explanation.

## Related runbooks, controls, examples, and templates

Use verification plans, findings, and release decisions with the dashboard-state
example. The Playwright chapter later supplies the executable full suite.
