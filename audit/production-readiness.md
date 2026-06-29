# Production Readiness Report — Cutctx

**Date:** 2026-06-29
**Scope:** Current local worktree verification in `/Users/aryansingh/Documents/Claude/Projects/headroom`

## Summary
Cutctx is in materially better shape than the older `v0.26.0` readiness snapshot suggested, but the repo still has a few meaningful risks that should keep us precise about release language.

This verification pass confirmed:
- Supply-chain signing and SBOM generation are already wired in CI.
- The `/v1/compress` product endpoint works end to end again after fixing two regressions.
- CCR retrieval, compression observability, and wrap persistence paths pass their focused suites.
- Dashboard savings headline math, attribution payloads, trend request counts, and history loading states were corrected in code and covered with fresh targeted tests.
- Fresh benchmark numbers are reproducible locally, but they do **not** support a blanket "best in market" compression-ratio claim on all corpora.
- The React dashboard release surface can be exercised live at `/dashboard`, including protected auth flow and live savings panels, when the dev proxy and local proxy share the same admin key.

## What Was Fixed In This Pass

### 1. `/v1/compress` was incorrectly admin-gated
File:
- [cutctx/proxy/routes/admin.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/routes/admin.py)

Issue:
- The compression-only endpoint was registered under admin auth dependencies, which contradicted product docs and broke SDK-style usage.

Fix:
- Removed admin/RBAC gating from `/v1/compress`.

Impact:
- Compression-only flows now behave like a product surface again instead of an operator-only endpoint.

### 2. Real compressed requests crashed savings bookkeeping
File:
- [cutctx/proxy/savings_tracker.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/savings_tracker.py)

Issue:
- Compressed requests hit a `NameError: name 'entry' is not defined` while recording history rows.

Fix:
- Replaced the bad `entry.get(...)` references with the actual per-request `delta_ghost_tokens` and `delta_scaffolding_tokens` counters.

Impact:
- `/v1/compress` now succeeds for large tool-output and multimodal requests instead of returning `503`.

### 3. Explicit compaction now explains and accepts smaller wins
Files:
- [cutctx/proxy/handlers/openai/compress.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/handlers/openai/compress.py)
- [cutctx/transforms/content_router.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/transforms/content_router.py)
- [cutctx/transforms/pipeline.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/transforms/pipeline.py)

Issue:
- The direct compression endpoint was still inheriting proxy-conservative acceptance behavior, so smaller but still real wins were often discarded without any useful explanation.
- A stricter balanced run could also poison the skip-cache and stop a later aggressive run from retrying the same content.

Fix:
- Added request-level diagnostics that surface content-router summary, threshold, route counts, cache behavior, and timing.
- Added an explicit `max_savings` profile for `/v1/compress`.
- Prevented stricter skip-cache decisions from blocking later looser acceptance thresholds.

Impact:
- The same repetitive assistant payload that stayed unchanged in `balanced` mode (`849 -> 849`, `0` saved) now compresses under `max_savings` (`849 -> 823`, `26` saved), with diagnostics explaining both outcomes.

### 4. Dashboard savings totals and enterprise status pages were telling partial truths
Files:
- [cutctx/proxy/cost.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/cost.py)
- [cutctx/proxy/server.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/server.py)
- [cutctx/proxy/routes/admin.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/routes/admin.py)
- [dashboard/src/lib/dashboard-context.jsx](/Users/aryansingh/Documents/Claude/Projects/headroom/dashboard/src/lib/dashboard-context.jsx)
- [dashboard/src/pages/Overview.jsx](/Users/aryansingh/Documents/Claude/Projects/headroom/dashboard/src/pages/Overview.jsx)
- [dashboard/src/pages/Capabilities.jsx](/Users/aryansingh/Documents/Claude/Projects/headroom/dashboard/src/pages/Capabilities.jsx)
- [dashboard/src/pages/Firewall.jsx](/Users/aryansingh/Documents/Claude/Projects/headroom/dashboard/src/pages/Firewall.jsx)

Issues:
- Session-level dollars saved excluded provider-cache savings even when the cache breakdown reported real savings.
- `/stats.savings_by_source` only emitted five legacy sources, while the dashboard expected newer attribution buckets too.
- The trend chart could overcount requests when both rollups and recent request rows were present.
- `/stats-history` failures collapsed into a misleading empty state instead of showing explicit loading/error status.
- Synthetic history fallback rows displayed `0` in fields that were actually unknown.
- `GET /rbac/roles` was guarded like a write surface, and the firewall page expected counters the backend did not truly expose.

Fixes:
- Cost summary now counts provider-cache savings in `total_saved_usd`, `without_cutctx_usd`, and cost savings percent.
- `/stats` now exposes the newer savings-source keys used by the dashboard.
- Overview cards now distinguish all-layer savings from active compression and avoid false zeroes / false request counts.
- History fetch status is explicit in the React state, and synthetic rows leave unknown values blank.
- RBAC role listing now uses a read-level permission already understood by the enterprise RBAC runtime.
- Firewall status surfaces truthful configuration/pattern inventory data and marks block counters as unavailable instead of implying zero.

Impact:
- The dashboard code is now aligned with the intended savings story and no longer understates cache-backed wins in the UI logic.
- Enterprise operator surfaces are less misleading about what is truly measured versus merely configured.

## Fresh Verification Evidence

### Targeted product-path tests
Executed on 2026-06-29:

- `./.venv/bin/python -m pytest tests/test_proxy_compress_endpoint.py tests/test_compression_observability.py -q`
  - Result: `22 passed`
- `./.venv/bin/python -m pytest tests/test_ccr_row_drop_store_bridge.py -q`
  - Result: `9 passed`
- `./.venv/bin/python -m pytest tests/test_cli/test_wrap_persistent.py tests/test_cli/test_wrap_rtk_metrics.py -q`
  - Result: `29 passed`

These cover:
- compression-only endpoint behavior
- multimodal compression reporting
- savings/observability surfaces
- CCR compress-to-retrieve round-trips
- persistent wrap state and RTK metrics behavior

### Extended regression bundle
Executed on 2026-06-29:

- `./.venv/bin/python -m pytest tests/test_proxy_compress_endpoint.py tests/test_compression_observability.py tests/test_ccr_row_drop_store_bridge.py tests/test_cli/test_wrap_persistent.py tests/test_cli/test_wrap_rtk_metrics.py tests/test_product_capabilities.py tests/test_proxy_savings_history.py tests/test_proxy_dashboard_stats_cache.py tests/test_savings_metadata.py tests/test_savings_metadata_response_headers.py tests/test_proxy_anthropic_compression_diagnostics.py -q`
  - Result: `152 passed`
- `cd dashboard && ../.venv/bin/python -m pytest ../tests/test_dashboard_cache_ttl_playwright.py -q`
  - Result: `1 passed`
- `cd dashboard && npx playwright test e2e/ui.spec.js e2e/overview.spec.js e2e/auth.spec.js`
  - Result: `7 passed`
- `pytest -q tests/test_proxy_dashboard_stats_cache.py tests/test_savings_hot_path.py tests/test_management_api_entitlements.py`
  - Result: `27 passed`

Important regression fixed during this sweep:
- [cutctx/proxy/outcome.py](/Users/aryansingh/Documents/Claude/Projects/headroom/cutctx/proxy/outcome.py)
  - `request_logger.log(...)` had escaped its `if request_logger is not None` guard and could crash Anthropic request handling with `AttributeError: 'NoneType' object has no attribute 'log'`, causing `502` responses in diagnostic coverage. The guard is now restored.

### Build / compile checks
- `./.venv/bin/python -m py_compile cutctx/proxy/routes/admin.py cutctx/proxy/savings_tracker.py`
  - Result: pass
- `./.venv/bin/python -m py_compile cutctx/proxy/outcome.py`
  - Result: pass

### Compression benchmark evidence
Executed on 2026-06-29:

- `./.venv/bin/python benchmarks/run_all.py --dry-run --output /tmp/cutctx_bench_results.json`

Fresh local dry-run scores:

| Corpus | Input tokens | Output tokens | Reduction | Latency |
|---|---:|---:|---:|---:|
| JSON | 8112 | 3326 | 59.0% | 743.6 ms |
| Code | 921 | 921 | 0.0% | 3565.3 ms |
| Prose | 607 | 607 | 0.0% | 29.5 ms |
| Mixed | 1108 | 760 | 31.4% | 655.8 ms |

### Comparative benchmark evidence
Executed on 2026-06-29:

- `./.venv/bin/python benchmarks/compare.py --tool cutctx --tool llmlingua2 --corpus synthetic --corpus mixed --dry-run --output /tmp/cutctx_compare_results.json`

Observed outcome:
- On the current dry-run `synthetic` and `mixed` corpora, Cutctx and LLMLingua2 produced the same output-token counts.
- Cutctx retained a much smaller reported model footprint in that harness: `280 MB` vs `4200 MB`.

Interpretation:
- The current local evidence supports a footprint and product-integration advantage.
- It does **not** support a universal "best compression ratio in market" claim from this benchmark alone.

### Live product checks
Executed on 2026-06-29:

- Live dashboard auth + overview:
  - React dashboard at `http://127.0.0.1:4173/dashboard` successfully moved from auth overlay to live metrics when the browser stored the actual proxy admin key.
  - Observed live surfaces included:
    - overview metrics with non-zero lifetime savings
    - trend chart hover details including tokens saved, requests, and model mix
    - honest `Request count unavailable` messaging for buckets without request rollups
    - recent-requests table with `Total saved`, `Direct`, `Scaffold`, and `Ghost` columns
- Protected compression endpoint:
  - `POST /v1/compress` with `profile=max_savings` on a repetitive assistant log payload returned:
    - `tokens_before=648`
    - `tokens_after=127`
    - `tokens_saved=521`
    - `transforms_applied=["router:log:0.15"]`
    - populated diagnostics with content-router summary and timing

Environment note:
- The Vite dashboard dev server is mounted at `/dashboard`, not `/`.
- For local manual QA, the dashboard dev server and the proxy should share the same `CUTCTX_ADMIN_API_KEY` or the operator should expect the auth overlay until the correct key is entered.
- If the local proxy process was already running before these dashboard/backend stat fixes were applied, restart it before using live `/stats` output as evidence. A stale process can still serve the old summary math and attribution shape even though the worktree is fixed.

## Supply Chain Status
The older note claiming "No image signing / SBOM" is stale.

Verified CI assets:
- [/.github/workflows/docker.yml](/Users/aryansingh/Documents/Claude/Projects/headroom/.github/workflows/docker.yml)
  - OIDC + cosign image signing flow present
- [/.github/workflows/publish.yml](/Users/aryansingh/Documents/Claude/Projects/headroom/.github/workflows/publish.yml)
  - CycloneDX SBOM generation present
- [/.github/workflows/sign-artifacts.yml](/Users/aryansingh/Documents/Claude/Projects/headroom/.github/workflows/sign-artifacts.yml)
  - artifact-signing workflow present

Status:
- Image signing / SBOM: `resolved in CI`

## Remaining Risks
These were not fully re-audited line by line in this pass, but they remain credible enough to keep on the release checklist:

- Neo4j default password risk called out in `RELEASE_REPORT.md`
- loopback admin-auth bypass behavior in `proxy/server.py`
- RBAC fail-open behavior when the checker is absent
- plaintext webhook secret storage
- Gemini savings tracking still marked incomplete in release reporting

## Release Guidance
Current recommendation:
- `Ready for continued product validation`

Not yet recommended:
- `Ready for broad "best-in-market" marketing claims`

Safe external claim after this pass:
- Cutctx has verified end-to-end compression, retrieval, observability, and wrap flows in the current worktree, with strong structured-data savings and materially smaller benchmarked model footprint than LLMLingua2 in the local comparison harness.

Unsafe external claim after this pass:
- Cutctx is categorically the best compressor on every workload or every benchmark.
