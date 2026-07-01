# Release Audit - 2026-07-01

## Recommendation
Status: `SHIP`

The current worktree is release-ready. The previously blocking runtime issues were fixed and re-verified in tests and against an isolated live proxy.

Important deployment note:
- Any already-running proxy process must be restarted to pick up these fixes.
- Earlier local runtimes on `127.0.0.1:8792` were inspected before the fixes landed, so their stale behavior should not be used as the release verdict.

## What Was Fixed

### 1. Firewall runtime wiring
The active runtime `create_app()` path did not initialize the firewall scanner or pass it into the admin router.

Fixed in:
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)

Verified by:
- `tests/test_firewall_runtime_routes.py`
- live isolated proxy on `127.0.0.1:8796`
  - `GET /firewall/status` returned `enabled: true`
  - `POST /firewall/scan` returned an injection violation and `block: true`

### 2. Team / cross-agent memory query path
The dashboard expected `/v1/memory/query`, but the EE memory API only exposed sync/review and the runtime never initialized the EE memory store.

Fixed in:
- [cutctx_ee/memory_service/api.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx_ee/memory_service/api.py)
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)
- [tests/test_memory_service_routes.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_memory_service_routes.py)
- [tests/test_memory_runtime_routes.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_memory_runtime_routes.py)

Verified by:
- router-level test coverage
- runtime app test coverage
- live isolated proxy on `127.0.0.1:8796`
  - `POST /v1/memory/sync` succeeded
  - SQLite row confirmed in `/tmp/cutctx-memory-8796.db`
  - `POST /v1/memory/review` succeeded
  - `GET /v1/memory/query?org_id=release-org&workspace_id=release-ws&limit=5` returned the stored item

### 3. Model routing boot path
The code that bootstrapped `ModelRouter()` existed only in the earlier shadowed `create_app()` definition, not in the active runtime app used by the shipped proxy.

Fixed in:
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)
- [tests/test_model_routing_runtime_boot.py](/Users/aryansingh/Documents/Claude/Projects/headroom/tests/test_model_routing_runtime_boot.py)

Verified by:
- `tests/test_model_routing_runtime_boot.py`
- `tests/test_model_router.py`
- live isolated proxy on `127.0.0.1:8796`
  - `GET /stats` returned:
    - `config.orchestrator = true`
    - `model_routing.requested = true`
    - `model_routing.available = true`
    - `model_routing.configured_routes = 1`

## Dashboard / UI State

### Governance
Status: `VERIFIED`

Evidence:
- optional features render as toggles again
- restart-required features still expose toggles, with restart messaging
- canonical config route remains `/config/flags`

### Orchestrator
Status: `VERIFIED`

Evidence:
- runtime stats now report boot-time router availability when `CUTCTX_MODEL_ROUTING` is set
- toggle path remains covered by `tests/test_dashboard_orchestrator.py`

### Memory
Status: `VERIFIED`

Evidence:
- query endpoint now exists
- live readback succeeded after sync/review
- dashboard memory surface now has a real backend path instead of a guaranteed `404`

## Verification Summary

### Focused Python suites
Passed:
- `uv run pytest tests/test_model_routing_runtime_boot.py tests/test_memory_service_routes.py tests/test_memory_runtime_routes.py tests/test_firewall_runtime_routes.py tests/test_dashboard_orchestrator.py tests/test_proxy_dynamic_init.py -q`
- `uv run pytest tests/test_model_router.py -q`

### Frontend build
Passed:
- `cd dashboard && npm run build`

### Live isolated proxy
Verified on:
- `http://127.0.0.1:8796`

Successful checks:
- `GET /health`
- `GET /stats`
- `GET /firewall/status`
- `POST /firewall/scan`
- `POST /v1/memory/sync`
- `POST /v1/memory/review`
- `GET /v1/memory/query`

## Residual Notes

- A routed completion was not demonstrated through the `mock` backend because LiteLLM rejects `mock/<model>` provider strings for completion-style calls. This is a limitation of the mock verification environment, not the router boot fix itself.
- The file still contains two `create_app()` definitions. The active runtime path is now functionally corrected, but a future cleanup pass should remove the shadowed duplicate to reduce maintenance risk.

## Release Verdict

`SHIP`

The code changes required to make governance toggles, firewall, memory, and orchestrator release-ready are in place and verified. Restart the deployed proxy process when promoting this build.
