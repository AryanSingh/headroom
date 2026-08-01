# Orchestration Dashboard Live E2E Audit — 2026-07-29

## Verdict

The Orchestrator dashboard is organized into three task-oriented workspaces—Operate, Contracts, and Configuration—and every exposed mutation has browser coverage through the production FastAPI app. The live suite does not fulfill production requests with Playwright route mocks. Forced rejection, concurrency, and stale-response behavior remains in the mocked suite because those states must be deterministic.

Status: **complete for the exposed dashboard control matrix**.

## Test boundary

- `dashboard/e2e/orchestrator-live.spec.js` launches the production `create_app` path with isolated temporary orchestration stores and authenticated admin routes.
- The provider dependency is a deterministic loopback FastAPI stub. No paid or external provider is called.
- `dashboard/e2e/orchestrator.spec.js` owns forced 5xx responses, delayed acknowledgements, revision conflicts, stale polling, and duplicate-submit checks.
- `tests/test_dashboard_orchestrator_policy_e2e.py` exercises the packaged dashboard against the proxy with Python Playwright; it was run with no skips.

## Control matrix

| Workspace | Exposed control or behavior | Production-route evidence | Rejection or edge evidence |
| --- | --- | --- | --- |
| Global | Operate, Contracts, Configuration selection | Live smoke loads authenticated state; all workspaces are traversed by live tests | `separates operate contracts and configuration into primary workspaces`; keyboard navigation assertions |
| Operate | Off, Auto, Aggressive | `Operate persists Off Auto and Aggressive through production config`; API state and reload asserted | Existing exact-acknowledgement, mismatch, stale optimism, and newest-generation tests |
| Operate | Turn Safe Savings off | `Operate turns Safe Savings off through the confirmed production path`; confirmation and API state asserted | `keeps Safe Savings on after a rejected disable and recovers on retry` |
| Operate | Compatibility provider enable/disable | `Operate disables and re-enables a compatibility provider`; `/v1/providers` state asserted | Provider errors remain visible inside the explicit diagnostics disclosure |
| Operate | Diagnostics disclosure and next action | Live tests traverse disclosure for Safe Savings and provider controls | `keeps the live command surface focused and diagnostics collapsed` |
| Contracts | New immutable draft and reload | `Contracts saves simulates promotes rolls back and pauses through production routes` saves v2 through the UI | Revision-conflict test preserves the local draft and prevents false persistence |
| Contracts | Deterministic simulation | Same live test runs draft simulation and asserts zero provider calls | Mocked preview asserts selected/rejected route evidence |
| Contracts | Start shadow | Same live test starts shadow through the UI and confirms v2 | Quality-gate mocked tests cover collecting and blocked evidence |
| Contracts | Promote to canary and active | Same live test seeds evidence through production API, then promotes through UI controls | Unsafe promotion is blocked by mocked quality evidence |
| Contracts | Roll back and pause | Same live test rolls back to v1, pauses, and asserts final persisted states | Lifecycle remains visible as Draft → Simulate → Shadow → Canary → Active |
| Configuration | Provider account and credential | `Configuration manages a provider credential connection and model refresh`; server response is checked for secret redaction | `reports a partial provider credential failure and succeeds on retry` |
| Configuration | Test connection and refresh models | Same live provider test calls the deterministic provider through production adapters | Error state is retained without a false success notice |
| Configuration | Remove credential | Same live provider test confirms destructive action and asserts credential removal through API | Confirmation is required and mutation state disables the active removal control |
| Configuration | Add role and default binding | `Configuration persists roles bindings settings preview search and keyboard navigation`; persisted config asserted | Dirty state appears before save; failed saves retain edits |
| Configuration | Selector binding add/edit/toggle/delete | Same live configuration test performs all four operations and asserts selectors, capabilities, enabled state, and deletion through API | Literal newline parsing defect was caught and fixed; retry path covered at config family level |
| Configuration | Routing settings | Same live test saves mode, policy, retries, timeout, and cooldown; API state asserted | `keeps a failed configuration save dirty and recovers on retry` |
| Configuration | Duplicate save protection | Live configuration save produces acknowledged state | `disables duplicate configuration saves while one request is pending` |
| Configuration | Route preview | Same live test previews the saved role and asserts the assigned model | Mocked eligibility evidence covers candidate scoring and rejection explanations |
| Configuration | Search and nested keyboard tabs | Same live test searches discovered models and uses Home navigation | Mocked primary and nested tab tests assert roving focus and one active tab stop |

## Responsive and accessibility evidence

- `all primary workspaces stay reachable and unobscured at desktop and 390px` captures six full-page screenshots under `dashboard/output/playwright/orchestrator/`.
- At 390px the test asserts document overflow is at most one pixel, the top bar is in normal document flow, the workspace navigation begins below it, and each primary tabpanel is reachable.
- The inspected desktop and mobile captures show no dashboard chrome covering active controls. Nested tab strips intentionally scroll horizontally on narrow screens.
- Primary and nested tabs expose ARIA tablists, selection, tabpanels, roving `tabIndex`, Arrow keys, Home, and End behavior.
- The activity table is a labeled, keyboard-focusable horizontal scroll region.

## Verification record

| Command | Result |
| --- | --- |
| `cd dashboard && npm test` | 29 passed |
| `cd dashboard && npx playwright test e2e/orchestrator.spec.js --project=chromium --workers=1` | 31 passed |
| `cd dashboard && npx playwright test e2e/orchestrator-live.spec.js --project=live-proxy --workers=1` | 7 passed |
| Focused orchestration pytest command from the implementation plan | 126 passed, 0 skipped, 1 deprecation warning |
| `cd dashboard && npm run lint` | Passed with zero warnings |
| `cd dashboard && npm run build` | Passed; production bundle generated |
| `uvx ruff@0.9.4 check dashboard tests/fixtures/orchestration_e2e_server.py` | Passed after import formatting |

## Defects found while closing the matrix

1. A failed configuration save could replace a valid empty configuration with the fatal “API unavailable” view. Initial-load errors and mutation errors now have separate state.
2. A partial provider-account success followed by credential failure was immediately erased by the refresh path. The refresh now completes before the partial-failure alert is published.
3. Selector bindings split the literal characters `\\n` instead of real newline-delimited selector rows. Parsing now uses actual newline characters.
4. The starter contract defaulted to an unregistered provider/model. It now uses the deterministic starter deployment expected by the live control plane.
5. Configuration tabs lacked complete keyboard navigation and the mobile header could remain sticky over workspace content. Both behaviors now match the accessibility and responsive contract.

## Residual limitations

- The provider stub proves production adapter and dashboard integration without proving a third-party provider's availability. External-provider certification belongs in staging smoke tests, not this deterministic suite.
- Screenshots are local verification artifacts and are ignored by Git; the test regenerates all six at the documented paths.
