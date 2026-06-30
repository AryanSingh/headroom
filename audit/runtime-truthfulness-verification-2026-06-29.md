# Runtime Truthfulness Verification — 2026-06-29

This note captures what was explicitly re-verified in the current worktree after the dashboard and capability-reporting changes.

## Newly verified in this pass

- `python -m cutctx.cli.main capabilities --json` works in a lean install.
  - Root cause fixed: eager CLI imports were pulling in unrelated optional dependencies such as `httpx`.
  - Current behavior: the CLI loads commands lazily and reports unavailable optional features instead of crashing.

- `/v1/compress` no longer fails healthy requests with a generic `503`.
  - Root cause fixed: `cutctx/proxy/handlers/openai/compress.py` imported `classify_client` from a stale module path.
  - Current behavior: normal compression requests complete and still record request outcomes.

- Runtime capability claims are more truthful.
  - Audio is reported as `pass-through`, not compressed.
  - Optional extras such as Graphify, Drain3, LLMLingua, image/OCR, and difftastic are surfaced separately from core proxy availability.

- Graphify status is operator-visible through `/stats`.
  - The payload now distinguishes `requested`, `available`, `active`, `status`, `reason`, and `interceptor_registered`.
  - Ready states also surface graph counts when an indexer is present.

## Commands and suites re-run

- `python3 -m cutctx.cli.main capabilities --json`
- `uv run python -m pytest -q tests/test_cli_capabilities.py tests/test_proxy_compress_endpoint.py`
- `uv run python -m pytest -q tests/test_cli_capabilities.py tests/test_proxy_compress_endpoint.py tests/test_proxy_dashboard_stats_cache.py tests/test_modality_matrix.py tests/test_product_capabilities.py tests/test_graphify_index.py tests/test_drain3_compressor.py tests/test_difftastic_interceptor.py tests/test_image_compression.py`
- `cd dashboard && npm run build`

## Important remaining limit

This does not prove every optional OSS capability is live in the current machine environment.

Several optional features still depend on runtime extras actually being installed, for example:

- `graphifyy`
- `networkx`
- `drain3`
- `llmlingua`
- `PIL`

That means the product is now better at telling the truth about missing capabilities, but a full "everything works live here" claim still requires those extras to be installed and exercised end to end.
