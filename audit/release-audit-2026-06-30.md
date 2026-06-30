# Release Audit — 2026-06-30

## Scope

This audit re-checked the latest audit report in `audit/comprehensive-capability-report.md`
against the current worktree and current test/runtime evidence. The report was treated as
advisory, not authoritative.

## Verified stale items from the latest report

- `searchQuery` dead-state claim is stale.
  - Current dashboard routes pass `searchQuery` into page components and the pages consume it.
- `/admin/config/flags` undocumented claim is stale.
  - Current repo documents it in the dashboard docs page and in wiki docs.
- team memory sync partial claim is stale.
  - `tests/test_memory_sync.py` passes in the current worktree.
- legacy proxy mode alias claim is stale.
  - Current `cutctx/proxy/modes.py` normalizes only `token` and `cache`.

## Verified real issues found during this audit

- Graphify availability detection was inconsistent with the current environment.
  - Runtime environment exposes `graphify`, while parts of Cutctx only probed `graphifyy`.
  - Impact: capabilities and Graphify availability could be reported as unavailable even when
    the installed dependency was present under the alternate package name.
- dashboard / stats compatibility drift after app-factory recovery work.
  - The runtime stats payload had drifted from the contract expected by the dashboard/proxy tests:
    missing `tokens.saved`, `requests.total`, `savings.by_layer`, and older feature-availability keys.
- documentation drift around `[all]`.
  - Several docs/wiki pages still implied `[all]` meant literally everything, which contradicted
    current package metadata.

## Changes made

### Runtime / proxy

- Restored a working `create_app()` runtime path in `cutctx/proxy/server.py` by overriding the
  malformed earlier factory with a clean app factory at the bottom of the module.
- Reinstated provider route registration for the verified app factory.
- Restored expected stats payload compatibility fields:
  - `tokens.saved`
  - `tokens.input`
  - `requests.total`
  - `savings.by_layer.cli_filtering`
  - `savings.by_layer.compression.tokens`
  - `savings.by_layer.compression.cli_filtering_tokens`
  - `savings.by_layer.compression.rtk_tokens`
  - `savings.by_layer.compression.lean_ctx_tokens`
  - `savings.by_layer.compression.all_layers_tokens`
- Restored truthful optional-feature keys under `feature_availability`:
  - `knowledge_graph`
  - `text_compression_engine`
  - `log_template_mining`
  - `structural_diff_engine`
  - `multimodal_image`
  - `smart_crusher`
  - `kompress`
  - `html_extractor`
  - `voice_filler`
  - `code_ast`
  - `audio`

### Graphify

- Updated capability detection to treat either `graphify` or `graphifyy` as a valid Graphify install.
- Updated Graphify runtime helpers to support either import path.
- Added a regression test covering the package-name alias case.

### Docs

- Updated README, dashboard docs, docs installation page, and wiki pages to stop describing
  `[all]` as literally “everything”.

## Evidence

### Runtime capability command

- `uv run python -m cutctx.cli.main capabilities --json`
  - `knowledge_graph.available = true`
  - `llmlingua.available = true`

### Tests re-run

- `uv run python -m py_compile cutctx/proxy/server.py cutctx/graph/graphify.py`
  - passed
- `uv run python -m pytest -q tests/test_proxy_runtime_truthfulness.py tests/test_provider_proxy_routes.py tests/test_proxy_dashboard_stats_cache.py tests/test_proxy_savings_history.py tests/test_proxy_compress_endpoint.py tests/test_proxy_anthropic_compression_diagnostics.py tests/test_graphify_index.py tests/test_cli_capabilities.py tests/test_memory_sync.py`
  - passed
  - 114 tests green in this audit slice
- `cd dashboard && npm run build`
  - passed

### Additional release-readiness checks re-run later in the audit

- `uv run python -m pytest -q tests/test_provider_codex_runtime.py tests/test_provider_gemini_runtime.py tests/test_openai_codex_routing.py`
  - passed after restoring health endpoints, startup/shutdown initialization, and `requests.by_model`
- `uv run python -m pytest -q tests/test_product_capabilities.py tests/test_modality_matrix.py tests/test_llmlingua_compressor.py tests/test_provider_codex_runtime.py tests/test_provider_gemini_runtime.py tests/test_openai_codex_routing.py tests/test_docs_truthfulness.py`
  - all passed except the Codex runtime slice before the runtime-health/stats fixes above
- `uv run python -m pytest -q tests/test_proxy_runtime_truthfulness.py tests/test_provider_proxy_routes.py tests/test_proxy_dashboard_stats_cache.py tests/test_proxy_savings_history.py tests/test_proxy_compress_endpoint.py tests/test_proxy_anthropic_compression_diagnostics.py`
  - passed again after migrating the clean app factory to lifespan startup/shutdown

## Current release-readiness view

### Strongly supported by current evidence

- provider passthrough routes are wired and tested
- dashboard stats endpoints are populated and contract-compatible with the current tests
- `/v1/compress` works and updates runtime stats
- Graphify capability detection is aligned with the current environment
- LLMLingua runtime surface is present again in the current worktree
- memory sync is working in the audited path

### Remaining caution

- `cutctx/proxy/server.py` still contains large historically malformed sections earlier in the file.
  - The current runtime is stabilized by the clean bottom-of-module `create_app()` override.
  - This is acceptable for current verified surfaces, but the older malformed body should eventually
    be cleaned out rather than left in place.
- Enterprise integrity warnings are still present in this environment when constructing `CutctxProxy`.
  - These warnings did not block the audited open/proxy runtime slices above, but they are still a
    release-readiness concern for enterprise packaging/integrity expectations.

## Verdict

The latest report was only partially current. Several claimed issues were stale, and the real
release blockers in the current worktree were Graphify truthfulness, stats contract drift, and
install/docs truthfulness. Those issues were remediated and re-verified in the audited slice above.
