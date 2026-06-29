# Headroom v0.28.0 — Incomplete / Half-Baked / Stubbed Features

> **Research-only audit.** No code was changed. Report documents what is incomplete, deprecated, retired, stubbed, or questionable.

---

## 🔴 RETIRED — Code Removed, Docs Still Active

### 1. IntelligentContextManager

| Field | Detail |
|---|---|
| **Status** | ✅ RETIRED (PR-B1, April 2026) |
| **Evidence** | `cutctx/transforms/pipeline.py:63`: *"Phase B PR-B1 retired the IntelligentContextManager / RollingWindow message-dropping branch. Live-zone-only compression is the sole strategy going forward."* |
| **Code** | `cutctx/transforms/intelligent_context.py` **does not exist.** |
| **Proxy** | `server.py` sets `self._context_manager_status = "passthrough"` — hardcoded no-op. |
| **Docs** | Still documented as active in 4+ wiki pages (`transforms.md`, `configuration.md`, `integration-guide.md`, `cli.md`). Flag `--no-intelligent-context` referenced in docs but does nothing. |
| **Recommendation** | Either remove all doc references, or re-implement. Currently a documentation liability. |

---

## 🟠 AMBIGUOUS — Live Code But Claimed Retired

### 2. LLMLingua-2 Compressor

| Field | Detail |
|---|---|
| **Status** | ⚠️ Contradictory |
| **Code** | `cutctx/transforms/llmlingua_compressor.py` — **fully implemented, imported, and wired** into `ContentRouterConfig` |
| **pyproject.toml** | Lines 99-103 still define `[llmlingua]` extra with `llmlingua>=0.2.0`, `torch`, `transformers`. However line 107 says *"The legacy [llmlingua] extra was removed in 0.9.x"* — contradictory within the same file. |
| **Proxy startup** | `server.py:386` still checks `config.use_llmlingua` and wires it to router config |
| **Exports** | `cutctx/transforms/__init__.py:235-240` still exports `LLMLinguaCompressor` |
| **Docs** | Multiple files say it's "retired" in favor of Kompress |
| **[all] extra** | Line 296 does NOT include `[llmlingua]` — so it's excluded from bulk install but still live |
| **Recommendation** | Commit: either fully remove the code and extra, or un-retire it. Current state confuses users. |

---

## 🟡 DISABLED BY DEFAULT — Features That Exist But Never Run

### 3. CacheAligner

| Field | Detail |
|---|---|
| **Code** | `cutctx/transforms/cache_aligner.py` — full implementation |
| **Pipeline** | `server.py:421`: `CacheAligner(CacheAlignerConfig(enabled=False))` — **hardcoded disabled** |
| **Docs** | Listed as an active transform stage |
| **Status** | Never runs. Implementation may be stale from disuse. |
| **Recommendation** | Either remove or fix and enable. |

### 4. Intelligence Layer (6 features)

| Feature | Lines of Code | Disabled By Default | CLI Flag? |
|---------|--------------|--------------------|-----------|
| Task-aware compression | 425 lines | ✅ `False` | ❌ env-only |
| Semantic dedup | 404 lines | ✅ `False` | ❌ env-only |
| Context budget controller | 505 lines | ✅ `False` | ❌ env-only |
| Cross-session profiles | 425 lines | ✅ `False` | ❌ env-only |
| Multi-agent shared context | 919 lines | ✅ `False` | ❌ env-only |
| Cost forecasting + policy | 535 lines | ✅ `False` | ❌ env-only |

**Status:** All 6 modules have real implementations (404-919 lines each) with imports wired into both Anthropic and OpenAI handler flows. When `any_enabled()` returns True, `pre_compression()` and `post_compression()` are called. However:

- **No CLI flags.** Activation is env-var only (`CUTCTX_TASK_AWARE_ENABLED=1`, etc.). Zero discoverability.
- **No proxy startup log.** When enabled, there's no banner line confirming activation.
- **No dashboard visibility.** The `/admin/intelligence/*` status endpoints exist but no UI surface.
- **Recommendation:** Add CLI flags, startup logging, and dashboard integration if these are production-ready. Otherwise they're dead code that looks complete but nobody uses.

### 5. Ensemble Model Routing

| Field | Detail |
|---|---|
| **Code** | `cutctx/proxy/ensemble.py` — exists |
| **Default** | `ensemble_enabled: bool = False` |
| **Evidence** | Not wired into any handler flow by default. Requires env activation. |

### 6. Firewall (LLM Guardrails)

| Field | Detail |
|---|---|
| **Code** | `cutctx/security/firewall.py` (555 lines) + `firewall_ml.py` |
| **Default** | `firewall_enabled: bool = False` |
| **Wired?** | Yes — `server.py:2416` creates firewall scanner when enabled |
| **Status** | ✅ Working when enabled. But users don't know it exists (no CLI flag in `--help`, no startup banner). |
| **Recommendation** | Add `--firewall` CLI flag for discoverability. |

---

## 🔵 STUBBED / PARTIAL IMPLEMENTATIONS

### 7. TOIN (`get_recommendation()` — Deprecated, Returns None)

| Field | Detail |
|---|---|
| **Code** | `cutctx/telemetry/toin.py:972-979` |
| **Status** | `get_recommendation()` always returns `None` since PR-B5. Logs a deprecation warning when called. |
| **Reason** | Observation-only since PR-B5 (fixed P2-27/P5-56 bugs). Recommendations now built offline via `toin_publish` script. |
| **Impact** | Any code path still calling `get_recommendation()` gets no value. The `compression-hint envelope` is gone. |
| **Recommendation** | Remove the dead method or mark clearly in all docs/calling code. |

### 8. Memory EE Routes — Stub Router

| Field | Detail |
|---|---|
| **Code** | `cutctx/proxy/routes/memory.py:35-86`: `_build_stub_router()` |
| **Status** | Returns **501 Not Implemented** for enterprise memory endpoints when EE is not installed |
| **Design intent** | Intentional — prevents 404 errors. But users may not understand why memory endpoints don't work. |
| **Risk** | The stub is silent. No startup log saying "EE memory endpoints disabled — install headroom-ee for full functionality." |

### 9. Memory Bridge — Only Syncs Legacy DB

| Field | Detail |
|---|---|
| **Code** | `cutctx/proxy/server.py:781-788` |
| **Status** | Markdown ↔ Headroom sync only works with the legacy single-file DB (`memory.db`). Per-project memory bridging is documented as a follow-up. |
| **Quote** | *"The Memory Bridge binds to the single legacy backend at `legacy_db_path`. Be aware that only the legacy DB syncs with markdown — per-project bridge sync is a follow-up planned."* |
| **Recommendation** | Complete per-project bridge support or remove the claim. |

### 10. Wrap Command Discrepancy

| Field | Detail |
|---|---|
| **Docs** | `wiki/index.md` and `wiki/cli.md` claim `cutctx wrap windsurf`, `cutctx wrap zed`, `cutctx wrap opencode` |
| **CLI reality** | `cutctx wrap --help` does NOT list these — only `aider, claude, copilot, codex, cursor, openclaw` |
| **Status** | Windsurf, Zed, and OpenCode may exist as hidden commands or were removed. Documentation is ahead of implementation. |

### 11. Report `schedule-cancel` Command — Duplicated

| Field | Detail |
|---|---|
| **Code** | `cutctx/cli/report.py` — `schedule_cancel` appears twice in source |
| **Status** | Likely a copy-paste overload that should be reviewed. One version may be dead code. |
| **Evidence** | Grep found two `def schedule_cancel` definitions in the same file. |

### 12. MCP Server — Three Implementations

| File | Purpose |
|------|---------|
| `cutctx/mcp_server.py` | Primary MCP server? |
| `cutctx/memory/mcp_server.py` | Memory-specific MCP server |
| `cutctx/ccr/mcp_server.py` (370 lines) | CCR-distribution MCP server |

**Status:** Unclear which is the canonical MCP server. Multiple implementations create confusion for users and maintenance burden. The `cutctx mcp serve` CLI command should reference the canonical one.

### 13. Billing — URL Opener, No Local Logic

| Field | Detail |
|---|---|
| **Code** | `cutctx/cli/billing.py` (120 lines) |
| **Status** | Both `checkout` and `portal` commands delegate entirely to `pitchtoship.com`. They open a URL in the browser and print it. No billing data is handled locally. |
| **Notable** | No self-serve tier enforcement, no license key generation from CLI, no local billing state. |
| **Risk** | If PitchToShip is down, billing is completely inoperable. |

---

## 📋 LEGACY CODE BURDEN

The codebase carries significant legacy compatibility weight:

| Area | Evidence |
|------|----------|
| **Legacy CCRStore wrapper** | `cutctx/ccr/store.py` wraps `BatchContextStore` with a legacy `put(original, ttl_seconds=300)` API |
| **Legacy JSON forwarder mode** | `legacy_json_kwarg` — an alternative body re-encoding path kept for backward compat |
| **Legacy state file migration** | Subscription tracker (`tracker.py:842-858`) parses pre-PR-G2 state files with fallback logic |
| **Legacy mode aliases** | `--mode token_mode`, `cache_mode`, `token_savings`, `cost_savings`, `token_cutctx` — 5 aliases for 2 actual modes |
| **Legacy DB path detection** | `server.py:769-778` checks for legacy single-file DB and migrates silently |
| **SmartCrusher legacy paths** | Multiple `legacy` comments in `smart_crusher.py` for pre-ContentRouter direct-call paths |
| **Legacy `CUTCTX_TELEMETRY_DISABLED`** | `collector.py:755` still checks the legacy env var name |
| **Legacy `CUTCTX_SAVINGS_PATH`** | `savings_tracker.py:61` preserves legacy behavior |
| **Legacy `CUTCTX_TOIN_PATH`** | `toin.py:162` preserves legacy behavior |

---

## 📊 Summary Table

| # | Feature | Status | Lines | Risk |
|---|---------|--------|-------|------|
| 1 | IntelligentContextManager | 🔴 RETIRED (docs still active) | N/A | User confusion |
| 2 | LLMLingua | 🟠 Contradictory | 4 files | User confusion |
| 3 | CacheAligner | 🟡 Hardcoded disabled | ~200 | Stale code |
| 4 | Intelligence Layer (6 features) | 🟡 Disabled, no CLI flags | 3,213 total | No discoverability |
| 5 | TOIN `get_recommendation()` | 🔵 Deprecated, returns None | ~30 | Dead code |
| 6 | Memory EE stub router | 🔵 Intentional 501 | ~50 | Silent degredation |
| 7 | Memory bridge (legacy-only) | 🔵 Partial — per-project TBD | ~20 | Follow-up drift |
| 8 | Wrap windsurf/zed/opencode | 🔵 Docs but no CLI | N/A | Doc drift |
| 9 | Report schedule-cancel dup | 🔵 Duplicate code | ~15 | Potential bug |
| 10 | MCP server (3 impls) | 🔵 Unclear canonical | ~600+ | Maintenance burden |
| 11 | Billing URL opener | 🔵 Thin wrapper | 120 | No local logic |
| 12 | Ensemble | 🟡 Disabled by default | ? | Dead code |
| 13 | Firewall | 🟡 Working but hidden | 555 | No discoverability |
| 14 | Legacy code burden | 📋 10+ legacy compat paths | hundreds | Maintenance drag |

**Total documented: 14 items** (1 retired, 1 ambiguous, 5 disabled-by-default, 7 stubbed/partial, plus a substantial legacy code burden across 10+ backward-compat paths.)
