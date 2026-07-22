# Dashboard Metric Card Balance Design

## Goal

Use the available horizontal space in Overview metric cards at narrow viewport
widths without changing the dashboard's visual identity or reducing the
readability of the primary metric.

## Scope

Update the Overview metric-card presentation only. Navigation, desktop layout,
data fetching, and metric semantics remain unchanged.

## Design

Each metric card retains its existing label, value, accent icon, and supporting
detail. Below the desktop breakpoint, its content becomes a two-column internal
layout:

- The left column holds the label and primary metric value.
- The right column holds the accent icon and supporting detail, right-aligned.
- The optional trend remains below the primary value within the left column.

Cards remain vertically stacked. This preserves comfortable touch targets and
avoids shrinking long metric values while using the previously empty right side
for information that already belongs to the card.

At very small widths, the card may return to a single-column layout if the two
columns would cause text collision or overflow.

## Accessibility and states

The change uses layout CSS only: semantic markup, accessible names, keyboard
behavior, and data values are unchanged. Loading skeletons adopt the same
internal visual balance. The layout must remain legible in dark and light
themes and at narrow and desktop viewports.

## Verification

1. Add a focused test that asserts the metric card renders its primary and
   supporting content in the new layout structure.
2. Run the dashboard test suite and production build.
3. Inspect the authenticated dashboard in a browser at phone and desktop
   viewport widths, confirming no horizontal overflow and no unused-card-width
   regression at the narrow layout.
