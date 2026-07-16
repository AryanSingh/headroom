# dashboard/src/data/

## Responsibility
Defines static capability-group metadata used to render and organize configurable Cutctx features.

## Design
`capabilities.js` exports declarative groups containing labels, descriptions, icons, flag keys, and feature presentation metadata; runtime status remains outside this directory.

## Flow
The Capabilities page imports the catalog, joins it with live stats/config flags, filters it for display, and emits toggle requests through dashboard API helpers.

## Integration
- Consumed by `pages/Capabilities.jsx`.
- Keys correspond to configuration flags exposed by the proxy.
