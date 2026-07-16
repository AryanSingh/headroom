# dashboard/src/components/

## Responsibility
Provides reusable presentation primitives and the interactive orchestration/routing editors used by dashboard pages.

## Design
`PageHeader` and `StatePanel` standardize page framing and empty/error/loading states. `RoleBindingEditor` manages RBAC binding edits. `OrchestrationStudio` visualizes topology and orchestrator state. `routing-studio/` is a cohesive contract-editing and rollout sub-application.

## Flow
Pages pass proxy snapshots, callbacks, and search/filter state into components. Editors maintain local form state, invoke supplied or module API mutations, then return acknowledgements so the owning page can refresh canonical data.

## Integration
- Consumed by `src/pages/` and the authentication shell in `App.jsx`.
- Uses Lucide icons and shared formatting/auth/API helpers from `src/lib/`.
- Delegates routing contract workflows to `routing-studio/`.
