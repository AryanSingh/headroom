# Dashboard Quiet Command Center Design

## Purpose

Evolve the Cutctx dashboard into a calm, premium operator console without
changing its route structure, API contracts, or operational workflows. The
dashboard should make health, savings, configuration, and investigation states
easy to scan while retaining the compact density needed by technical operators.

## Scope

Apply the visual system consistently to these existing routes:

- Dashboard
- Savings
- Orchestrator
- Capabilities
- Governance
- Security
- Memory
- Replay
- Playground
- Docs

The authentication view, desktop sidebar, mobile drawer, topbar, search,
theme toggle, empty states, unavailable states, error states, and loading
states are included. Backend behavior, endpoint shapes, routing logic, and
product copy semantics remain unchanged unless a small microcopy correction is
needed for clarity.

## Art Direction

The direction is a quiet command center: restrained, assured, and operational.
Use the existing dark/light themes and teal identity, but reserve saturated
color for important signal. The surface system should distinguish canvas,
working panels, and elevated configuration/action areas without relying on a
border around every element.

Typography should give route titles, key metrics, and panel headings clear
priority. Metadata, supporting explanations, and dense table information stay
legible but visually quieter. Motion is limited to short, opacity and transform
based transitions; all new motion must respect reduced-motion preferences.

## Shared UI Patterns

### App shell

- Keep the existing sidebar/topbar layout and routes.
- Make the active navigation item more distinct through background, icon, and
  text emphasis rather than excessive decoration.
- Refine collapsed desktop and mobile drawer behavior so it remains obvious
  which navigation state is active.
- Retain keyboard shortcuts, skip link, Escape behavior, and visible focus.

### Page headers

Create a reusable page-header treatment that supports a route title, concise
operator context, status, and contextual actions. Pages that already have
controls retain them, but controls align to the header hierarchy rather than
competing with the title.

### Panels and metrics

Define reusable panel variants for summary, data, configuration, and alert
content. Their spacing, headings, metadata, and action placement should be
consistent across pages. Metric cards should make the primary value immediate,
then show status/trend context at a clearly secondary level.

### State panels

Introduce one composable state-panel pattern for loading, empty, unavailable,
partial-data, and error content. It should provide an optional icon, a direct
title, an operator-oriented explanation, and an optional retry or next action.
Authentication uses the same visual language while remaining focused and
accessible.

### Data-dense surfaces

Tables, event streams, code blocks, configuration rows, and filters retain
their information density. Improve grouping, row hover/focus treatment,
horizontal overflow behavior, and mobile wrapping without hiding critical data.

## Responsive and Accessibility Requirements

- Desktop, tablet, and phone layouts must retain readable density.
- Panels and controls must not introduce horizontal viewport overflow.
- Navigation, controls, dialogs/drawers, search, and tables remain keyboard
  usable with visible focus states.
- Semantic HTML remains preferred; ARIA is only added where native semantics
  are insufficient.
- Color is never the only indicator of health, risk, or selection.
- New transition rules include a `prefers-reduced-motion` fallback.

## Implementation Boundaries

- Extend existing CSS tokens and shared class patterns rather than introducing
  a second component library.
- Use existing React components and route contracts; extract small shared UI
  primitives only where they remove repeated markup or styling.
- Preserve the user’s current uncommitted dashboard and proxy changes. Any
  overlap must be reviewed before editing.
- Do not change proxy APIs or dashboard data schemas as part of this work.

## Verification

- Run dashboard lint and production build.
- Run existing dashboard E2E coverage.
- Inspect representative desktop and mobile views in the browser.
- Verify both themes, authentication, empty, error, unavailable, loading, and
  populated dashboard states.
- Verify sidebar navigation, drawer behavior, theme toggle, search keyboard
  shortcut, and visible focus behavior.

## Trade-offs

The design favors restraint and long-session readability over dramatic visual
effects. It avoids a wholesale component-system replacement, keeping the
change compatible with existing routes and data integrations. This means the
result will feel materially more intentional while retaining the product’s
recognizable operator-console structure.
