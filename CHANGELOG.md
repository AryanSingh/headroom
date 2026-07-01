# Changelog

All notable changes to Cutctx will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Restored the admin/runtime source tree to a bootable state after a corrupted `cutctx/proxy/routes/admin.py` edit, and re-verified live current-source endpoints for `/health`, `/config/flags`, `/policy/status`, `/stats`, and `/stats-history`.
- Hardened dashboard operator data loading so unsupported or absent config surfaces no longer present as broken stats in local dashboard flows.

### Added

- Inline multimodal audio optimization for supported chat/compress flows, with targeted regression coverage in `tests/test_audio_compressor.py`, `tests/test_inline_audio_messages.py`, and `tests/test_proxy_compress_endpoint.py`.
- **Feedback Loop (Data Flywheel)** (`cutctx/ccr/response_handler.py`, `cutctx/proxy/intelligence_pipeline.py`, `cutctx/transforms/content_router.py`, `cutctx/proxy/server.py`, `cutctx/profiles.py`) — CCR response handler records retrievals as feedback → updates per-workspace `CompressionProfile` → `recommended_ratio` flows into `ContentRouterConfig.per_type_overrides` → adjusts `bias_multiplier` for affected content types. Enables adaptive compression based on retrieval patterns. Test coverage in `tests/test_feedback_loop.py` (11 tests).
- **Stack-graph reachability bridge** (`cutctx/graph/reachability.py`, `cutctx/transforms/code_compressor.py`) — symbol reachability analysis for Stack Graphs core, with `extract_symbol_names()`, `resolve_entry_points()`, and wiring into `CodeCompressor.set_protected_symbols()` for syntax-preserving code compression. Distinct from the Stack Graphs AST/TSG core released in [0.29.0]. Test coverage in `tests/test_stack_graph_reachability.py` (17 tests) and `tests/test_initiative2_e2e.py` (5 tests).
- **Benchmark CLI** (`cutctx evals benchmark`) — comprehensive compression evaluation harness with `BenchmarkRunner`, 10 guarded compressor adapters (smart_crusher, log, search, diff, code, kompress, llmlingua, drain3, content_router, all), ThreadPoolExecutor parallelism, JSON and markdown output (LLMLingua-paper-style comparable format). Supports `--dataset {tool_outputs,longbench,squad,hotpotqa}`, `--compressors`, and `--metrics {ratio,tokens_saved,f1,rouge_l,information_recall,exact_match}`. Zero-LLM by default. Test coverage in `tests/test_evals_benchmark.py` (6 tests).

## [0.29.0] - 2026-06-30

### Added
- **USearch vector backend** (`cutctx/memory/backends/usearch_store.py`) — new optional vector index backend using Unum's USearch library for ~10× faster vector search with f16 quantization and zero-copy memory-mapped index loading. Added `VectorBackend.USEARCH` enum; wired into factory with `AUTO` fallback chain (USEARCH → SQLITE_VEC → HNSW). Requires `pip install usearch>=2.10.0`.
- **Stack Graphs Rust module** (`crates/cutctx-core/src/stack_graph/`) — GitHub-style stack-graph implementation for deterministic, file-incremental cross-file code navigation. `StackGraphManager` with language registration (Python + JS/TS), tree-sitter AST parsing, TSG rule loading for scoped symbol resolution, and BFS-based `resolve_reference()` for go-to-definition across files.
- **PyO3 binding** (`crates/cutctx-py/src/lib.rs`) — `StackGraphManager` exposed to Python as `cutctx._core.StackGraphManager` with thread-safe mutex wrapping.
- **Python facade** (`cutctx/graph/resolver.py`) — `StackGraphResolver` with `index_project()`, `index_file()`, `resolve()`, file/node count properties.
- **Proxy integration** (`cutctx/cli/proxy.py`, `cutctx/proxy/models.py`, `cutctx/proxy/server.py`) — `--stack-graph` CLI flag (`CUTCTX_STACK_GRAPH=1` env var), background indexing, `/stats` exposure.
- **CodeGraphWatcher integration** (`cutctx/graph/watcher.py`) — incremental stack graph re-indexing on file change.
- **Documentation** — `wiki/stack-graphs.md` (full feature docs), `wiki/memory.md` (USearch section), `wiki/index.md` (feature entries), `wiki/plans/2026-06-30-usearch-stack-graphs-integration-plan.md` (integration plan with ADRs).

### Changed
- **`pyproject.toml`** — added `usearch>=2.10.0` to `[memory]` optional-dependency group
- **`crates/cutctx-core/Cargo.toml`** — added `stack-graphs`, `tree-sitter`, `tree-sitter-stack-graphs`, `tree-sitter-python`, `tree-sitter-javascript`, `lsp-positions`, `streaming-iterator` dependencies
- **`crates/cutctx-core/src/lib.rs`** — added `pub mod stack_graph;`
- **`cutctx/memory/config.py`** — added `VectorBackend.USEARCH = "usearch"` enum member
- **`cutctx/memory/factory.py`** — added `USEARCH` routing with availability check and fallback
- **`cutctx/memory/backends/__init__.py`** — added lazy import for `UsearchMemoryBackend`
- **`cutctx/graph/__init__.py`** — added `StackGraphResolver` and `stack_graph_available()` to re-exports

### New Files
- `cutctx/memory/backends/usearch_store.py` — `UsearchMemoryBackend` class (thread-safe, persistent, f16 quantization)
- `crates/cutctx-core/src/stack_graph/mod.rs` — `StackGraphManager` with TSG rule loading and `resolve_reference()`
- `crates/cutctx-core/src/stack_graph/tsg_rules/python.tsg` — Python TSG definitions
- `crates/cutctx-core/src/stack_graph/tsg_rules/javascript.tsg` — JavaScript/TypeScript TSG definitions
- `crates/cutctx-py/src/py_stack_graph.rs` — PyO3 `PyStackGraphManager` wrapper
- `cutctx/graph/resolver.py` — `StackGraphResolver` Python facade
- `tests/test_usearch_backend.py` — 11 tests for USearch backend (skipif guard)
- `tests/test_stack_graph_resolver.py` — 12 Python-level stack graph tests
- `crates/cutctx-core/tests/test_stack_graphs.rs` — 6 Rust integration tests
- `wiki/stack-graphs.md` — Stack Graphs documentation page
- `wiki/plans/2026-06-30-usearch-stack-graphs-integration-plan.md` — full integration plan

### Documentation
- `wiki/memory.md` — Added USearch backend section with config options, auto-preference chain, and architecture diagram update
- `wiki/index.md` — Added Stack Graphs feature card, updated memory entry to mention USearch, added usearch to installation extras

### Security
- **CRITICAL**: Stripped `/dashboard`, `/api/savings`, `/api/models` from loopback auth bypass path (server.py:213) — localhost no longer skips auth for these endpoints
- **CRITICAL**: LIKE wildcard injection fix — added `_escape_like()` helper and `ESCAPE "\\"` clause for entity_ref LIKE queries in sqlite.py
- **HIGH**: Kompress max-input DoS guard — added `CUTCTX_KOMPRESS_MAX_WORDS` env var (default 80,000 words) limiting per-call text input
- **MEDIUM**: Added startup-time `logger.warning` when `CUTCTX_ALLOW_DEBUG` is set

### Fixed
- 56 ruff auto-fixable lint errors resolved (F401 unused imports, trailing whitespace, etc.)

## [0.28.0] - 2026-06-29

### Added
- **`cutctx capabilities` command** — new CLI command to display all available compression capabilities, formats, algorithms, and configuration options
- **Pass-through audio routing** — audio requests pass through unmodified when compression is not applicable
- **Documentation improvements** — expanded README guidance on install extras and CLI commands

### Fixed
- **README install guidance** — clarified distinction between recommended/full install (`pip install "cutctx-ai[all]"`) and granular extras
- **Audio compression documentation** — documented pass-through behavior for non-compression scenarios


## [0.26.1] - 2026-06-23

### Security
* **Hardware fingerprint hardening**: replaced `uuid.getnode()` (MAC address, trivially spoofed) with OS-native machine IDs — `/etc/machine-id` on Linux, `IOPlatformUUID` via `ioreg` on macOS, `HKLM\MachineGuid` on Windows. Three-factor binding: machine ID + hostname + username.
* **HMAC signature expanded 64-bit → 128-bit**: `licensing.rs` truncation changed from 16 → 32 hex chars with constant-time XOR fold comparison and up-front length rejection. `generate_license.py` updated to emit 32-char signatures.
* **Anti-debug guard**: Rust module `antidebug.rs` — macOS `ptrace(PT_DENY_ATTACH)`, Linux `TracerPid` parse, Windows `IsDebuggerPresent`. Python fallback in `cutctx/security/antidebug.py`. `CUTCTX_ALLOW_DEBUG=1` escape hatch. Called automatically at EE import time.
* **EE binary integrity manifest**: `cutctx_ee/MANIFEST.sha256.json` — SHA-256 hashes of all `.so` files, HMAC-signed with `CUTCTX_LICENSE_HMAC_SECRET`. Verified by `cutctx/security/integrity.py` before any EE code executes. `CUTCTX_SKIP_INTEGRITY_CHECK=1` escape hatch for debugging.

### Fixed
* **Stateless mode** (`--stateless` / `CUTCTX_STATELESS=true`): 14 files updated to use `:memory:` SQLite; beacon lock files, file logging, and subscription file persistence all guarded. Zero files written in stateless mode (was 20+).
* **Docker**: `COPY cutctx_ee/` was missing from `Dockerfile`, causing `ImportError` at container start. Fixed with correct COPY directives, extras (`proxy,code,ee`), `--no-editable` install, and EE manifest rebuild for Linux platform.
* **Proxy routes**: `/audit/stats` returned 404 (now 403 for non-enterprise); `/v1/spend/query` returned 500 (now 200 with NullStore fallback); `/v1/dsr/export` and `/v1/dsr/delete` had wrong prefix (`/v1/me` → `/v1/dsr`).
* **CLI** (from manual testing pass): `bench --algorithm` six implementations replacing broken `_get_algorithms()`; `agent-savings` duplicate `--format` option removed; `audit` broken import removed; `learn --dry-run` flag added; `evals probes` empty-directory guard.
* **Compression**: `compact_table.py` `compress()` was returning `None`; `diff_compressor.py` Python fallback added for when Rust produces no compression; `log_compressor.py` missing `tokens_saved_estimate` field; `selective_filter.py` wrong return type.
* **LlamaIndex Pydantic v2 compatibility**: `CutctxNodePostprocessor` fields now use class-level annotations and `PrivateAttr`.
* **Air-gap mode**: `is_offline()` now checks both `CUTCTX_AIR_GAP=1` and `CUTCTX_OFFLINE_MODE=1`; proxy refuses to start without `CUTCTX_LICENSE_HMAC_SECRET` in air-gap mode.
* **EE integrity check on source installs**: `verify_ee_manifest` now detects when zero `.so` files are present (fresh clone / uncompiled dev install) and skips gracefully instead of raising `IntegrityError`.

### Added
* **JetBrains plugin CI verification**: `pluginVerification.ides` block added to `build.gradle.kts` — verifies against IntelliJ IDEA Community 2024.1, 2024.3, and 2025.1 (the full declared `sinceBuild=241` / `untilBuild=251.*` range).
* **`CCRStore`**: backward-compatible wrapper (`cutctx/ccr/store.py`) exposing legacy `put()`/`get()` API over `BatchContextStore`.
* **Missing package inits**: `cutctx_ee/memory_service/__init__.py` and `cutctx_ee/tests/__init__.py` added (were causing `ImportError` in Docker).

### Fixed
* **pyproject.toml URLs**: corrected typo `AryanSingh/cutcxt` → `cutctx/cutctx` in Repository, Issues, and Changelog URLs
* **README badge URLs**: all 5 `AryanSingh/cutcxt` badge and star-history URLs corrected to `cutctx/cutctx`

### Added
* **PRIVACY.md**: new document covering local-first architecture, CCR store location, `--stateless` / `--no-telemetry` modes, API key pass-through, enterprise VPC deployment, and explicit "what Cutctx does NOT do" list
* **Image optimization documented**: README and proxy `--help` now surface the `image_optimize` capability (40–90% reduction, zero config, on-by-default)
* **Accuracy guard documented**: `CUTCTX_ACCURACY_GUARD=strict|balanced|off` surfaces in README near proxy configuration
* **LLMLingua-2 integration** (`pip install cutctx-ai[llmlingua]`): Microsoft's BERT-level ML token-classification compressor now available as an optional algorithm. Use `cutctx proxy --llmlingua` or `CUTCTX_USE_LLMLINGUA=1`. Falls through to Kompress gracefully when not installed. Provides a second ML compression path independent of the Kompress/ModernBERT stack.
* **CompactTableCompressor**: new pure-Python transform that serializes JSON arrays of homogeneous objects into a compact pipe-delimited table format (30–60% smaller than JSON for file listings, DB rows, search results, API list responses). Auto-activates for arrays of ≥5 dicts before SmartCrusher; constant columns collapsed to header annotations.
* **Query-aware compression** (`--query-aware` / `CUTCTX_QUERY_AWARE=1`): detects the user's task type from the last message (CODE, DEBUG, SEARCH, LIST, SUMMARIZE, etc.) and automatically adjusts `protect_recent` and `min_tokens_to_crush` per compression pass. CODE/DEBUG: conservative (protect last 6 turns). SEARCH/LIST/SUMMARIZE: aggressive (protect last 2 turns). Uses existing `TaskType` feature extractor infrastructure.
* **JetBrains plugin**: raised `pluginUntilBuild` from `243.*` to `251.*` so the plugin is compatible with IntelliJ 2025.1+ (build 251)
* **Langfuse integration surfaced** (`pip install cutctx-ai[langfuse]`): `cutctx proxy --langfuse` (or `CUTCTX_LANGFUSE_ENABLED=1`) now activates the built-in Langfuse OTEL tracing with visible CLI flag, startup banner line, and `[langfuse]` installable extra. Added `wiki/langfuse.md`.
* **LlamaIndex integration** (`pip install cutctx-ai[llamaindex]`): `CutctxNodePostprocessor` — drop-in LlamaIndex `NodePostprocessor` that filters retrieved nodes by BM25/hybrid relevance score and optionally compresses surviving node text via Cutctx ContentRouter. Added `wiki/llamaindex.md`.
* **Selective Context Filter** (`--selective-filter` / `CUTCTX_SELECTIVE_FILTER=1`): new pre-compression transform that scores each conversation turn against the current user query and drops turns below `--selective-filter-threshold` (default 0.15). Uses existing BM25/hybrid relevance infrastructure. Wired into `ContentRouterConfig` and runs before all compression logic.

### Added
* **`cutctx init windsurf`**: now performs real durable install — writes `openai.baseUrl` to the platform-correct Windsurf `settings.json` (macOS/Linux/Windows paths resolved automatically); merges non-destructively with existing settings
* **`cutctx init zed`**: now performs real durable install — writes `language_models.openai.api_url` and `language_models.anthropic.api_url` into `~/.config/zed/settings.json` via deep-merge
* **`cutctx init opencode`**: now performs real durable install — injects `OPENAI_BASE_URL` into the user's shell profile using the existing marker-block mechanism (same pattern as Copilot/Gemini)
* **`cutctx proxy --ccr-ttl-seconds`**: configurable CCR store TTL (default 1800s / 30 min; `0` = never expire). Also controllable via `CUTCTX_CCR_TTL_SECONDS` env var. Removes the silent-data-loss risk on long agent runs and enables persistent/daemon deployments with no expiry
* **e2e wrap smoke tests**: added `verify_windsurf_wrap`, `verify_zed_wrap`, `verify_opencode_wrap` to `e2e/wrap/run.py` following the `--prepare-only` pattern used by cline/continue/goose/openhands

### Added

* **harnesses — Windsurf:** `cutctx wrap windsurf` starts the proxy and prints OpenAI and Anthropic base URL configuration instructions for Windsurf's Settings UI and `settings.json`. Provider module at `cutctx/providers/windsurf/`. `cutctx init windsurf` prints manual shell-profile setup instructions.
* **harnesses — Zed:** `cutctx wrap zed` starts the proxy and prints the exact `language_models.openai.api_url` / `language_models.anthropic.api_url` JSON snippet for `~/.config/zed/settings.json`. Provider module at `cutctx/providers/zed/`. `cutctx init zed` prints manual setup instructions.
* **harnesses — opencode:** `cutctx wrap opencode` starts the proxy and launches opencode with `OPENAI_BASE_URL` pointed at the local proxy — same Pattern A as `cutctx wrap codex`. `cutctx init opencode` prints manual shell-profile instructions. Added `opencode` and `windsurf` to `_AGENT_SAVINGS_WRAP_AGENTS` for per-session savings attribution.
* **VS Code extension:** full TypeScript extension at `extensions/vscode/` — auto-starts the `cutctx proxy` process, polls `/stats` every 30 s, shows tokens saved in the status bar, and configures Cline / Continue via command. Published as `cutctx-ai` on the VS Code Marketplace.
* **JetBrains plugin:** full Kotlin/Gradle plugin at `extensions/jetbrains/` for IntelliJ IDEA, PyCharm, and all JetBrains IDEs — `ProxyService` manages the proxy process lifetime, status bar widget shows live savings, settings configurable, Tools > Cutctx menu. Uses IntelliJ Platform Gradle Plugin v2.
* **distribution protection:** `scripts/strip_wheel.py` strips proprietary `.py` sources from built wheels (algorithms stay in compiled Rust `.so`). `scripts/build_protected_wheel.sh` runs the full maturin + strip pipeline in one command. `make dist-protected` target added. `PROTECTION.md` documents the protection architecture.
* **compress SKILL.md:** adversarially tested all five claims against live `cutctx-ai` v0.27.0 install; corrected binary name, removed non-existent CLI commands (`compress`, `stats`, `retrieve`), added proxy dependency note, fixed compression ratio claims, documented 30-minute CCR TTL.

* **kompress:** warn when `CUTCTX_KOMPRESS_BACKEND` is set to an unrecognized
  value instead of silently falling back to `auto`, and document the backend
  selection env var (`auto` / `onnx` / `onnx_cpu` / `onnx_coreml` / `pytorch` /
  `pytorch_mps` plus shorthand aliases) in `wiki/configuration.md` (issue
  [#202](https://github.com/chopratejas/cutctx/issues/202), PR
  [#204](https://github.com/chopratejas/cutctx/pull/204)).
* **proxy:** per-provider attribution in the savings history rollups. Each `/stats-history` bucket (hourly/daily/weekly/monthly) now carries a `by_provider` map breaking down `tokens_saved`, `compression_savings_usd_delta`, `total_input_tokens_delta`, and `total_input_cost_usd_delta` per provider, so consumers can show how savings and spend are distributed across providers within a time period. Providers only appear in a bucket where they moved a counter; legacy history checkpoints with no provider collapse into `"unknown"`. Affected files: `cutctx/proxy/savings_tracker.py`, `cutctx/proxy/prometheus_metrics.py`.
* **cli:** startup banner now includes a `Performance Tuning` section that surfaces active `CUTCTX_COMPRESSION_STABLE_AFTER_TURN`, `CUTCTX_STALE_READ_COMPRESS_AFTER_TURNS`, and embedding-server socket values when set; shows a hint to set them when all defaults are in use.

### Changed

* **deps:** loosen over-pinned constraints and add upper bounds
  - `litellm==1.82.3` -> `>=1.86.2,<2.0` (exact pin blocked security patches; floor stays above the CVE-2026-42271 fix)
  - `transformers>=4.30.0` -> `>=4.30.0,<6.0` (add upper bound; library already crossed a major version silently)
  - `sentence-transformers>=2.2.0` -> `>=2.2.0,<6.0` (same; applied in `memory`, `evals`, and `dev` extras)
  - `neo4j>=5.20.0` -> `>=5.20.0,<7.0` (client had already crossed the 5.x/6.x boundary)
  - `mem0ai>=0.1.100` -> `>=1.0.0,<2.0` (floor was pre-1.0; locked package is already 1.0.11)
  - `langchain-core>=0.2.0` -> `>=1.3.3,<4.0` (floor stays above current high-severity advisory fixes)
  - `langchain-openai>=0.1.0` -> `>=1.1.14,<2.0` (floor stays above current advisory fixes)
  - `qdrant-client>=1.9.0` -> `>=1.9.0,<2.0`
  - `uvicorn>=0.23.0` -> `>=0.23.0,<1.0` (applied in `proxy` and `dev` extras)
  - Same `transformers` and `litellm` bounds applied consistently across `ml`, `voice`, and `dev` extras
* **docker:** bump `neo4j` image in `docker-compose.yml` from `5.15.0` to `5.26` (latest 5.x LTS)
* **docker:** bump `UV_VERSION` in `Dockerfile` from `0.11.16` to `0.11.18`

### Bug Fixes

* **codex:** respect `CODEX_HOME` when `cutctx wrap codex` writes provider, MCP, memory, backup, and global `AGENTS.md` config, and warn when `unwrap codex` may be looking at the default Codex home because `CODEX_HOME` is unset.
* **proxy:** multi-worker CCR warning is now conditional on backend — when `CUTCTX_CCR_BACKEND` is unset (default `InMemoryBackend`, per-process), the startup warning includes CCR retrieval failures and suggests `CUTCTX_CCR_BACKEND=sqlite`; when a cross-worker backend is already configured, the warning covers only the remaining per-worker stores (compression cache, prefix tracker, TOIN, CostTracker). Updated `RUST_DEV.md` to accurately document Python `CompressionStore` as per-process by default.
* **deps:** move `gunicorn` to `[proxy-prod]` extra with `sys_platform != 'win32'` guard; removed from `[proxy]` to avoid forcing a Unix-only package on dev, CI, and Windows users ([#537](https://github.com/chopratejas/cutctx/pull/537))
* **startup:** suppress proxy startup log noise -- litellm banner, trafilatura parse errors, HuggingFace Hub unauthenticated warnings, tiktoken fallback warning, and httpx INFO lines from sentence_transformers HEAD checks. Affected files: `cutctx/providers/litellm.py`, `cutctx/transforms/html_extractor.py`, `cutctx/memory/adapters/embedders.py`, `cutctx/providers/anthropic.py`, `cutctx/providers/registry.py`, `cutctx/image/onnx_router.py`, `cutctx/transforms/kompress_compressor.py`.

### Security
- **`/debug/memory` loopback guard.** The endpoint was missing the
  `Depends(_require_loopback)` guard that all other `/debug/*` endpoints carry.
  External callers can no longer reach it.
- **`retry_max_attempts` zero guard.** When `retry_enabled=True` and
  `retry_max_attempts=0` the retry loop exited without setting `last_error`,
  causing `raise last_error` to raise `TypeError: exceptions must derive from
  BaseException`. A `RuntimeError` with an actionable message is now raised
  instead, and `ProxyConfig.__post_init__` rejects `retry_max_attempts < 1`
  at construction time.
- **Blocking subprocess on async event loop.** `_read_rtk_lifetime_stats` and
  `_read_lean_ctx_lifetime_stats` called `subprocess.run` directly on the
  asyncio thread. The `initialize_context_tool_session_baseline` function is
  now `async` and offloads the subprocess via `asyncio.to_thread`; the stats
  endpoint uses `await asyncio.to_thread(_get_context_tool_stats)`.
- **Hardcoded Neo4j credential in `docker-compose.yml`.** `NEO4J_AUTH` now
  defaults to `${NEO4J_AUTH:-neo4j/REPLACE_WITH_STRONG_PASSWORD}` and is documented in
  `.env.example` (excluded from `.gitignore` via `!.env.example`).
- **`SemanticCache.get_memory_stats()` concurrent iteration.** The method
  iterates `self._cache.values()` without holding the async lock. A snapshot
  is now taken via `list(self._cache.values())` before iterating to avoid
  `RuntimeError: dictionary changed size during iteration` under async load.
- **Default Neo4j password in `ProxyConfig`.** `memory_neo4j_password` default
  changed from `"password"` to `""`. The proxy startup path now emits a
  `logger.warning` when `memory_backend == "qdrant-neo4j"` and the password
  is empty, prompting operators to set a real credential.

### Fixed
- **PyPI install clarity and release gating.** Documented `pipx --python python3.13`
  for environments where unsupported Python wheel tags cause older-version
  resolution, made PyPI publish failures block GitHub Releases unless
  `PYPI_SKIP=true`, and added an sdist `LICENSE` invariant.

- **`cutctx learn` with claude-cli no longer fails silently on slow
  networks or large digests.** The CLI backend timeout was a hard 120s
  wall-clock cap with no liveness signal: a successful long analysis and
  a hung connection looked identical, and exit 0 with "no recommendations"
  was the only user-visible signal. Two changes:
  (1) **Streaming + idle timeout for claude-cli**: the command now uses
  `--output-format stream-json --verbose` and a watchdog thread reads
  events as they arrive. The process is killed only after
  `CUTCTX_LEARN_CLI_IDLE_TIMEOUT_SECS` (default 60s) of zero output, or
  after `CUTCTX_LEARN_CLI_TIMEOUT_SECS` (default 300s, was 120s) total.
  Long-but-active analyses run to completion; genuine hangs are caught
  fast. The final `type:"result"` event carries the assistant response.
  Drains stdout/stderr via reader threads so the watchdog works on
  Windows too. (2) **Env-var overrides for all CLI backends**:
  `CUTCTX_LEARN_CLI_TIMEOUT_SECS` is honored by gemini-cli and
  codex-cli as the wall-clock timeout; idle override applies only to the
  streaming claude-cli path.
- **`Learned: error recovery` section in MEMORY.md no longer bloats with
  stale, one-shot, or contradictory entries.** The matchers paired up
  unrelated tool calls (e.g. `state.rs` and `lib.rs` in the same dir
  becoming `File state.rs does not exist. The correct path is lib.rs.`),
  the dedup key was the literal rendered bullet text so near-duplicates
  each created their own row, the shutdown flush dropped the evidence
  gate to 1 so every singleton landed at session end, and there was no
  TTL or re-validation. Fixed at every layer:
  (1) **Emission**: Read recoveries require the failed/successful
  basenames to be identical or close in edit distance; Bash recoveries
  require a shared binary (allowing `python`↔`python3` and
  `ruff`↔`.venv/bin/ruff` variants) plus low-edit-distance OR a shared
  substantive non-flag token. Unrelated pairs are rejected at the source.
  (2) **Dedup**: error-recovery rows are hashed on recovery intent —
  Read on `(basename(error_path), basename(success_path))`, Bash on the
  primary command stripped of volatile suffixes (`| tail -N`, `2>&1`,
  etc.). Near-duplicates collapse into one row.
  (3) **Evidence gating**: default `min_evidence` raised from 2 to 5;
  shutdown-relaxation removed; new `--min-evidence` flag and
  `CUTCTX_MIN_EVIDENCE` envvar so embedded clients can tighten the
  threshold further.
  (4) **Render-time refinement**: drop rows not re-observed in 21 days,
  re-validate Read success paths against the filesystem, collapse
  same-error_path-with-multiple-targets into one "use Glob/Grep first"
  bullet, rank by `evidence_count * 0.5 ** (days/5)`, cap the section
  at 15. A→B / B→A contradiction pairs are also dropped at flush time.
  Patterns now stamp `first_seen_at` / `last_seen_at` on every save;
  `_bump_persisted_evidence` updates them via `json_set`. Other
  `Learned: …` categories (environment, preference, architecture) are
  untouched.
- **`cutctx unwrap codex` now actually undoes `cutctx wrap codex`** —
  previously there was no `unwrap codex` subcommand at all, so the injected
  `model_provider = "cutctx"` / `[model_providers.cutctx]` block stayed
  in `~/.codex/config.toml` forever and Codex continued routing through the
  (potentially stopped) proxy, surfacing as `Missing environment variable:
  OPENAI_API_KEY`. `wrap codex` now snapshots the pre-wrap
  `config.toml` to `config.toml.cutctx-backup` before its first injection,
  and `unwrap codex` restores that snapshot byte-for-byte (or, if the
  backup is missing, strips only the Cutctx-managed block and leaves
  surrounding user content intact). Safe no-op when run without a prior
  wrap. Reported by @raenaryl in Discord.
- **Image compressors now release shared router models after use and proxy shutdown** —
  the proxy/image compression path no longer keeps global `technique-router`
  and `SigLIP` model instances pinned in memory after one-off image
  optimization work. The `get_compressor()` helper now returns a fresh,
  caller-owned compressor instead of a process-lifetime singleton.
- **`cutctx learn` no longer clobbers prior recommendations on re-run** —
  the marker block in `CLAUDE.md` / `MEMORY.md` is now merged with the
  prior block instead of wholesale-replaced. Sections re-surfaced by the
  new run win; sections not re-surfaced are carried forward so learnings
  accumulate across runs instead of disappearing. To fully rebuild the
  block, delete it manually and re-run. (#231)
- **`cutctx learn` no longer emits dangling cross-references when a
  section is re-surfaced** — the analyzer now includes the project's
  current `<!-- cutctx:learn -->` block (from `CLAUDE.md` and
  `MEMORY.md`) in the LLM digest as a "Prior Learned Patterns" section,
  and the system prompt instructs the LLM that re-emitting a section
  replaces the prior one wholesale. Prevents bullets like "`X` is *also*
  large — same rule as `Y`, `Z`" from appearing after `Y` and `Z` got
  dropped during per-section replacement. The writer's section-level
  carry-forward from #231 remains in place as a safety net for sections
  the LLM omits entirely. New helper `extract_marker_block` added to
  `cutctx.learn.writer`.

### Added
- **`turn_id` linking agent-loop API calls to a single user prompt** — a new
  `compute_turn_id(model, system, messages)` helper in
  `cutctx/proxy/helpers.py` hashes the message prefix up to and including
  the last user-text message, yielding an id that is stable across every
  agent-loop iteration of one prompt but rolls over when the user sends a
  new prompt (or runs `/compact`, `/clear`). `RequestLog` gained a
  `turn_id: str | None` field, which is stamped at every log site
  (anthropic handler bedrock + direct branches, and the streaming handler)
  and surfaced as `turn_id` in `/transformations/feed`. Lets downstream
  consumers (e.g. the Cutctx Desktop Activity tab) aggregate savings per
  user prompt rather than per API call.
- **Live flush of traffic-learned patterns to CLAUDE.md / MEMORY.md** — the
  `TrafficLearner` now writes to agent-native context files continuously
  during proxy operation, not just at shutdown. A new dirty-flag debounced
  `_flush_worker` (10s window, `FLUSH_DEBOUNCE_SECONDS`) calls
  `flush_to_file()` whenever `_accumulate()` marks the learner dirty, so
  patterns surface in `CLAUDE.md` / `MEMORY.md` near real-time. Flushes
  read both persisted rows (via `_load_persisted_patterns_from_sqlite`)
  and the in-memory accumulator, bucket patterns by project via the learn
  plugin registry (`plugin.discover_projects()` + longest-path anchoring
  in `_project_for_pattern`), and route by `PatternCategory` to the
  correct file (`_patterns_to_recommendations` +
  `_CATEGORY_TO_TARGET`). Live flushes require `evidence_count >= 2`;
  the shutdown flush accepts single-evidence rows.

### Fixed
- **Traffic-learner evidence count stuck at 1; duplicate DB rows across
  restarts.** `_accumulate` queued patterns with the default
  `ExtractedPattern.evidence_count = 1` regardless of how many times the
  pattern was actually seen, so every persisted row landed at `1` and
  never crossed the live-flush gate (`evidence_count >= 2`). Worse, once
  a pattern was in `_saved_hashes` it was early-returned on every
  re-sighting, and `_saved_hashes` reset on process restart — so a second
  sighting in a later session inserted a duplicate row rather than
  bumping the existing one. Now: `_accumulate` writes the real
  accumulated count at save time, `start()` hydrates `_saved_hashes` +
  a new `_persisted_ids` map from the DB, and re-sightings bump the
  persisted row's `metadata.evidence_count` via an atomic `json_set`
  `UPDATE` (`_bump_persisted_evidence`). `_load_persisted_patterns_from_sqlite`
  now filters via `json_extract(metadata, '$.source')` instead of a
  LIKE on the raw JSON string, so rows survive metadata rewrites.

### Added
- **`CUTCTX_QDRANT_*` environment variables for memory Qdrant configuration**
  (#31) — `Memory(backend="qdrant-neo4j")`, `Mem0Config`, `MemoryConfig`, and
  `ProxyConfig` now resolve their Qdrant connection from
  `CUTCTX_QDRANT_URL`, `CUTCTX_QDRANT_HOST`, `CUTCTX_QDRANT_PORT`,
  `CUTCTX_QDRANT_API_KEY`, `CUTCTX_QDRANT_HTTPS`,
  `CUTCTX_QDRANT_PREFER_GRPC`, and `CUTCTX_QDRANT_GRPC_PORT`. Explicit
  constructor arguments still win; unset env keeps the existing
  `localhost:6333` defaults. Adds matching `--memory-qdrant-{url,host,port,api-key}`
  CLI flags. Enables hosted Qdrant (Qdrant Cloud) and shared/remote Qdrant
  stacks without code changes. New helper:
  [`cutctx/memory/qdrant_env.py`](cutctx/memory/qdrant_env.py).
- **Telemetry stack & install-mode identity fields** — anonymous beacon now
  reports `cutctx_stack` (how Cutctx is invoked: `proxy`, `wrap_claude`,
  `adapter_ts_openai`, ...) and `install_mode` (`wrapped` / `persistent` /
  `on_demand`), plus `requests_by_stack` for proxies that serve multiple
  integrations. Proxy exposes a `by_stack` bucket alongside `by_provider` /
  `by_model` on `/stats`, a matching `cutctx_requests_by_stack` Prometheus
  counter, and an `X-Cutctx-Stack` header honored by the FastAPI middleware.
  `cutctx wrap <tool>` sets `CUTCTX_STACK=wrap_<agent>`; the TS SDK and
  all four adapters (`openai`, `anthropic`, `gemini`, `vercel-ai`) tag their
  compress calls. Schema migration:
  [`sql/upgrade_telemetry_stack_context.sql`](sql/upgrade_telemetry_stack_context.sql).
- **Canonical filesystem contract** (issue #175) — new `CUTCTX_CONFIG_DIR`
  (default `~/.cutctx/config`, read-mostly) and `CUTCTX_WORKSPACE_DIR`
  (default `~/.cutctx`, read-write state) env vars recognized by the Python
  proxy/CLI and the npm SDK. Additive; all existing per-resource env vars
  (`CUTCTX_SAVINGS_PATH`, `CUTCTX_TOIN_PATH`,
  `CUTCTX_SUBSCRIPTION_STATE_PATH`, `CUTCTX_MODEL_LIMITS`) continue to
  work with identical semantics. Docker install scripts and
  `docker-compose.native.yml` forward the new vars into containers so
  savings, logs, and telemetry resolve to the bind-mounted `.cutctx` path.
  See [`wiki/filesystem-contract.md`](wiki/filesystem-contract.md).

### Changed
- **`/stats-history` now returns compact checkpoint history by default** — the
  JSON response keeps recent checkpoints dense while evenly sampling older
  checkpoints so long-running installs do not return ever-growing payloads.
  Add `history_mode=full` to fetch the full retained checkpoint list, or
  `history_mode=none` to skip it entirely while still receiving the derived
  hourly/daily/weekly/monthly rollups. Responses now include a
  `history_summary` block describing stored versus returned points.

### Fixed
- **Streaming Anthropic requests are now visible to `/stats.recent_requests`
  and `/transformations/feed`** — `_finalize_stream_response` did not call
  `self.logger.log(...)`, so the entire streaming Anthropic code path (the
  one Claude Code uses) silently bypassed the request logger. Only the
  non-streaming Anthropic path and the Bedrock streaming path were logged.
  As a consequence, `--log-messages` had no observable effect on the live
  transformations feed for typical traffic. The streaming finalizer now
  emits the same `RequestLog` shape the other paths do, including
  `request_messages` when `log_full_messages` is enabled.

### Added
- **Codex-proxy resilience hardening** — reduces event-loop starvation under cold-start reconnect storms
  - **Stage-timing instrumentation** — per-stage durations for both Codex WS accept and Anthropic `/v1/messages` pre-upstream phases emitted as a single `STAGE_TIMINGS` structured log line per request plus Prometheus histograms
  - **Per-pipeline shared warmup** — Anthropic + OpenAI pipelines eagerly load compressors/parsers once at startup; status merged into `WarmupRegistry` for `/debug/warmup` and `/readyz`
  - **WS session registry** — first-class tracking of active Codex WS sessions with deterministic relay-task cancellation and termination-cause classification (`client_disconnect`, `upstream_error`, `client_timeout`, etc.)
  - **Bounded pre-upstream Anthropic concurrency** — `--anthropic-pre-upstream-concurrency` / `CUTCTX_ANTHROPIC_PRE_UPSTREAM_CONCURRENCY` caps simultaneous `/v1/messages` pre-upstream work (body read, deep copy, first compression stage, memory-context lookup, upstream connect) so replay storms cannot starve `/livez`, `/readyz`, and new Codex WS opens. Default: auto `max(2, min(8, cpu_count))`; `0` or negative disables (unbounded)
  - **Loopback-only debug endpoints** — `/debug/tasks`, `/debug/ws-sessions`, `/debug/warmup` return `404` (not `403`) to non-loopback callers so external scanners cannot enumerate them
  - **Reconnect-storm repro harness** — `scripts/repro_codex_replay.py` drives concurrent WS + HTTP replay traffic against a local proxy and asserts `/livez` p99 under threshold; `--json` output routes JSON to stdout and the human summary to stderr
- **Proxy liveness and readiness health checks**
  - Adds `GET /livez` for process liveness and `GET /readyz` for traffic readiness
  - Keeps `GET /health` backward compatible while expanding it with readiness details and subsystem checks
  - Eagerly initializes configured memory backends during proxy startup so readiness reflects real serving capability
  - Wires `/readyz` into the Docker image `HEALTHCHECK` and the example `docker-compose.yml`
- **Durable proxy savings history**
  - Persists proxy compression savings history locally at `~/.cutctx/proxy_savings.json`
  - Supports `CUTCTX_SAVINGS_PATH` to override the storage location
  - Adds `/stats-history` with lifetime totals plus hourly/daily/weekly/monthly rollups
  - Supports JSON and CSV export from `/stats-history`
  - Extends `/stats` with a `persistent_savings` block while keeping `savings_history` backward compatible
  - Adds a historical mode to `/dashboard` backed by `/stats-history`, including export actions
- **Proxy telemetry SDK override** via `CUTCTX_SDK`
  - Downstream apps can override the anonymous telemetry `sdk` field without patching installed files
  - Blank values fall back to the default `proxy` label
- **`cutctx learn`** — Offline failure learning for coding agents
  - Analyzes past conversation history (Claude Code, extensible to Cursor/Codex)
  - **Success correlation**: for each failure, finds what succeeded after and extracts the specific correction
  - 5 analyzers: Environment, Structure, Command Patterns, Retry Prevention, Cross-Session
  - Writes specific learnings to CLAUDE.md (stable project facts) and MEMORY.md (session patterns)
  - Generic architecture: tool-agnostic `ToolCall` model, pluggable Scanner/Writer adapters
  - Dry-run by default, `--apply` to write, `--all` for all projects
  - Example output: "FirstClassEntity.java is not at axion-formats/ — actually at axion-scala-common/"
- **Read Lifecycle Management** — Event-driven compression of stale/superseded Read outputs
  - Detects when a Read output becomes stale (file was edited after) or superseded (file was re-read)
  - Replaces stale/superseded content with compact CCR markers, stores originals for retrieval
  - 75% of Read output bytes are provably stale or redundant (from real-world analysis of 66K tool calls)
  - Fresh Reads (latest read, no subsequent edit) are never touched — Edit safety preserved
  - Opt-in via `ReadLifecycleConfig(enabled=True)`, disabled by default
  - Handles both OpenAI and Anthropic message formats
- **any-llm backend** - Route requests through 38+ LLM providers (OpenAI, Mistral, Groq, Ollama, etc.) via [any-llm](https://mozilla-ai.github.io/any-llm/providers/)
  - Enable with `--backend anyllm --anyllm-provider <provider>`
  - Install with: `pip install 'cutctx-ai[anyllm]'`
- Production-ready proxy server with caching, rate limiting, and metrics
- CLI command `cutctx proxy` to start the proxy server

- **LLMLingua-2 Integration** (opt-in ML-based compression)
  - `LLMLinguaCompressor` transform using Microsoft's LLMLingua-2 model
  - Content-aware compression rates (code: 0.4, JSON: 0.35, text: 0.3)
  - Memory management utilities: `unload_llmlingua_model()`, `is_llmlingua_model_loaded()`
  - Proxy integration via `--llmlingua` flag
  - Device selection: `--llmlingua-device` (auto/cuda/cpu/mps)
  - Custom compression rate: `--llmlingua-rate`
  - Helpful startup hints when llmlingua is available but not enabled
  - ~~Install with: `pip install cutctx-ai[llmlingua]`~~ (the `[llmlingua]` extra was removed in 0.9.x)
- **Code-Aware Compression** (AST-based, syntax-preserving)
  - `CodeAwareCompressor` transform using tree-sitter for AST parsing
  - Supports Python, JavaScript, TypeScript, Go, Rust, Java, C, C++
  - Preserves imports, function signatures, type annotations, error handlers
  - Compresses function bodies while maintaining structural integrity
  - Guarantees syntactically valid output (no broken code)
  - Automatic language detection from code patterns
  - Memory management: `is_tree_sitter_available()`, `unload_tree_sitter()`
  - Uses `tree-sitter-language-pack` for broad language support
  - Install with: `pip install cutctx-ai[code]`
- **ContentRouter** (intelligent compression orchestrator)
  - Auto-routes content to optimal compressor based on type detection
  - Source hint support for high-confidence routing (file paths, tool names)
  - Handles mixed content (e.g., markdown with code blocks)
  - Strategies: CODE_AWARE, SMART_CRUSHER, SEARCH, LOG, TEXT, LLMLINGUA
  - Configurable strategy preferences and fallbacks
  - Routing decision log for transparency and debugging
- **Custom Model Configuration**
  - Support for new models: Claude 4.5 (Opus), Claude 4 (Sonnet, Haiku), o3, o3-mini
  - Pattern-based inference for unknown models (opus/sonnet/haiku tiers)
  - Custom model config via `CUTCTX_MODEL_LIMITS` environment variable
  - Config file support: `~/.cutctx/models.json`
  - Graceful fallback for unknown models (no crashes)
  - Updated pricing data for all current models

### Fixed
- **Event.wait task leak in subscription trackers** — `asyncio.shield` pattern prevents cancellation of the outer `wait_for` from leaking the inner `Event.wait` task
- **Python 3.10 compatibility for memory-context fail-open** — catches `asyncio.TimeoutError` (the 3.10-compatible alias) rather than `TimeoutError` to preserve behaviour on older runtimes
- **uvicorn `proxy_headers=False`** — refuses `Forwarded` / `X-Forwarded-For` rewrites so the loopback guard on `/debug/*` cannot be spoofed by a misconfigured reverse proxy
- **First-frame timeout for Codex WS accepts** — guards against a client that opens a handshake and never sends the first frame; relays cancel deterministically with `client_timeout`
- **Semaphore leak on unexpected exception in Anthropic pre-upstream path** — the finalizer now releases the pre-upstream semaphore on every exit path (early 4xx, cache hit, upstream error, streaming handoff)
- **`active_relay_tasks` gauge double-decrement** — `deregister_and_count` returns `(handle, released_task_count)` atomically so the handler decrements the Prometheus gauge by the exact number it registered, eliminating drift

### Internal
- **IPv6-mapped loopback recognition** — the loopback guard parses `::ffff:127.0.0.1` and other dual-stack literals through `ipaddress.ip_address(...).is_loopback`
- **Lock-free stage-timing accumulators** — `record_stage_timings` writes to per-path counters that do not contend with `/metrics` export or `record_request`
- **Narrow `contextlib.suppress` in relay classification** — only `CancelledError` is suppressed where we reclassify it; other exceptions propagate so termination cause stays truthful
- **`jitter_delay_ms` helper** — shared exponential-backoff + 50-150% jitter formula in `cutctx/proxy/helpers.py`; used by three proxy retry sites and mirrored inline in the repro harness

## [0.2.0] - 2025-01-07

### Added
- **SmartCrusher**: Statistical compression for tool outputs
  - Keeps first/last K items, errors, anomalies, and relevance matches
  - Variance-based change point detection
  - Pattern detection (time series, logs, search results)
- **Relevance Scoring Engine**: ML-powered item relevance
  - `BM25Scorer`: Fast keyword matching (zero dependencies)
  - `EmbeddingScorer`: Semantic similarity with sentence-transformers
  - `HybridScorer`: Adaptive combination of both methods
- **CacheAligner**: Prefix stabilization for better cache hits
  - Dynamic date extraction
  - Whitespace normalization
  - Stable prefix hashing
- **RollingWindow**: Context management within token limits
  - Drops oldest tool units first
  - Never orphans tool results
  - Preserves recent turns
- **Multi-Provider Support**:
  - Anthropic with official `count_tokens` API
  - Google with official `countTokens` API
  - Cohere with official `tokenize` API
  - Mistral with official tokenizer
  - LiteLLM for unified interface
- **Integrations**:
  - LangChain callback handler (`CutctxOptimizer`)
  - MCP (Model Context Protocol) utilities
- **Proxy Server** (`cutctx.proxy`):
  - Semantic caching with LRU eviction
  - Token bucket rate limiting
  - Retry with exponential backoff
  - Cost tracking with budget enforcement
  - Prometheus metrics endpoint
  - Request logging (JSONL)
- **Pricing Registry**: Centralized model pricing with staleness tracking
- **Benchmarks**: Performance benchmarks for transforms and relevance scoring

### Changed
- Improved token counting accuracy across all providers
- Enhanced tool output compression with relevance-aware selection

### Fixed
- Mistral tokenizer API compatibility
- Google token counting for multi-turn conversations

## [0.1.0] - 2025-01-05

### Added
- Initial release
- `CutctxClient`: OpenAI-compatible client wrapper
- `ToolCrusher`: Basic tool output compression
- Audit mode for observation without modification
- Optimize mode for applying transforms
- Simulate mode for previewing changes
- SQLite and JSONL storage backends
- HTML report generation
- Streaming support

### Safety Guarantees
- Never removes human content
- Never breaks tool ordering
- Parse failures are no-ops
- Preserves recency (last N turns)

---

## Migration Guide

### From 0.1.x to 0.2.x

The 0.2.0 release is backward compatible. New features are opt-in:

```python
# Old code still works
from cutctx import CutctxClient, OpenAIProvider

# New SmartCrusher (replaces ToolCrusher for better compression)
from cutctx import SmartCrusher, SmartCrusherConfig

config = SmartCrusherConfig(
    min_tokens_to_crush=200,
    max_items_after_crush=50,
)
crusher = SmartCrusher(config)

# New relevance scoring
from cutctx import create_scorer

scorer = create_scorer("hybrid")  # or "bm25" for zero deps
```

### Using the Proxy

New in 0.2.0 - run Cutctx as a proxy server:

```bash
# Start the proxy
cutctx proxy --port 8787

# Use with Claude Code
ANTHROPIC_BASE_URL=http://localhost:8787 claude
```

[Unreleased]: https://github.com/cutctx/cutctx/compare/v0.29.0...HEAD
[0.29.0]: https://github.com/cutctx/cutctx/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/cutctx/cutctx/compare/v0.26.1...v0.28.0
[0.26.1]: https://github.com/cutctx/cutctx/compare/v0.26.0...v0.26.1
[0.2.0]: https://github.com/chopratejas/cutctx/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/chopratejas/cutctx/releases/tag/v0.1.0
