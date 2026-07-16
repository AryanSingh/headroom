# dashboard/src/components/routing-studio/

## Responsibility
Implements the routing-contract control plane UI: contract discovery/editing, route simulation, decision-pipeline inspection, evidence review, and staged rollout controls.

## Design
`RoutingStudio` coordinates focused panels. `ContractList` and `ContractEditor` model selectable editable contracts; `RouteSimulator` exercises decisions; `DecisionPipeline` and `EvidencePanel` explain routing results; `RolloutPanel` manages deployment state. `api.js` isolates authenticated endpoint/fallback handling.

## Flow
The studio loads contracts and rollout state -> selection hydrates editor/simulator panels -> mutations call routing admin endpoints -> simulator responses feed pipeline and evidence views -> successful changes reload the canonical server state.

## Integration
- Embedded by `pages/Orchestrator.jsx`.
- Uses dashboard admin-auth and proxy URL helpers.
- Integrates with the proxy's routing contract, simulation, evidence, and rollout endpoints.
