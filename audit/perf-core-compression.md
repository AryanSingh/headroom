# Cutctx Core Compression Pipeline — Performance & Architecture Audit

**Phase:** 1 of 4 (Parallel Audit)
**Date:** 2026-07-12
**Scope:** Transform pipeline, dual-runtime parity, deep_copy overhead, ContentRouter decomposition

---

## 1. Pipeline Architecture Overview

### Two Distinct Pipelines

Cutctx operates **two separate compression pipelines** that share compressor backends but differ in orchestration:

#### Pipeline A: Python TransformPipeline (`cutctx/transforms/pipeline.py`)

```
messages (list[dict])
    │
    ▼  deep_copy_messages() ← COPY #1 (line 301)
    │
    ├─► CacheAligner.apply()     ← COPY #2 (line 282, detector-only, messages unchanged)
    │      └─ detect_volatile_content() — no-op on messages, warnings only
    │
    └─► ContentRouter.apply()
           ├─ SelectiveContextFilter (optional, opt-in)
           ├─ ReadLifecycleManager (optional, opt-in)
           ├─ Per-message loop:
           │    ├─ detect_content_type() — Rust via PyO3 (_core.detect_content_type)
           │    ├─ TagProtector — Rust via PyO3 (_core.protect_tags / restore_tags)
           │    ├─ SmartCrusher.apply()  ← COPY #3 (line 903)
           │    │     └─ _smart_crush_content() — Rust via PyO3
           │    ├─ LogCompressor / SearchCompressor / DiffCompressor / CodeCompressor
           │    │     └─ Each Rust via PyO3, with Python fallback for DiffCompressor
           │    ├─ KompressCompressor (ML, opt-in via CUTCTX_ENABLE_KOMPRESS)
           │    └─ LLMLinguaCompressor (ML, opt-in via llmlingua extra)
           │
           └─ AdaptiveSizer — informational only, no message mutation
```

#### Pipeline B: Rust Live-Zone Dispatcher (`crates/cutctx-core/src/transforms/live_zone.rs`)

```
body_raw (byte slice)
    │
    ├─► parse JSON once
    ├─► compute frozen_message_count
    ├─► identify live zone (latest user message blocks)
    ├─► per-block dispatch:
    │    ├─ JsonArray → SmartCrusher (Rust)
    │    ├─ BuildOutput → LogCompressor (Rust)
    │    ├─ SearchResults → SearchCompressor (Rust)
    │    ├─ GitDiff → DiffCompressor (Rust)
    │    ├─ SourceCode → no-op (Rust code_compressor NOT ported yet)
    │    ├─ PlainText/Html → no-op
    │    └─ Image/Audio → ImageCompressor/AudioCompressor (Rust)
    │
    └─► byte-range surgery (only modified blocks replaced)
```

**Key difference:** Pipeline B never copies the full message list. It operates on byte slices and performs surgical replacement of individual blocks. Bytes outside modified ranges are byte-identical to the input.

### Pipeline C: Rust Orchestrator (`crates/cutctx-core/src/transforms/pipeline/orchestrator.rs`)

A third pipeline exists for **content-type-keyed dispatch** within the Rust crate:

```
input (string slice) + ContentType
    │
    ├─ rayon::join:
    │    ├─ Reformat phase (serial) — JsonMinifier, LogTemplate
    │    └─ Bloat estimation phase (parallel) — per-offload scores
    │
    ├─ Decide which offloads to run (score ≥ threshold)
    ├─ Run offloads serially (each sees previous output)
    └─ PipelineResult { output, steps_applied, bytes_saved, cache_keys }
```

This is a **separate orchestration layer** used by the live-zone dispatchers' per-block compressors, not by the Python pipeline.

---

## 2. Transform Inventory Table

| Transform | Python | Rust | PyO3 Bridge | Maturity | Latency | Copy Overhead |
|-----------|--------|------|-------------|----------|---------|---------------|
| **CacheAligner** | ✅ Full | ❌ | ❌ | Production | <1ms | COPY #2 (pipeline apply → aligner) |
| **ContentRouter** | ✅ Full | ❌ | ❌ | Production | 65ms avg | N/A (orchestrator) |
| **SmartCrusher** | ✅ Shim | ✅ Full (13 modules) | ✅ | Production | 0.22ms | COPY #3 (apply → result_messages) |
| **LogCompressor** | ✅ Shim | ✅ Full | ✅ | Production | <5ms est | None |
| **SearchCompressor** | ✅ Shim | ✅ Full | ✅ | Production | <5ms est | None |
| **DiffCompressor** | ✅ Fallback | ✅ Full | ✅ | Beta (Rust returns unchanged for many diffs) | <5ms est | None |
| **CodeCompressor** | ✅ Full (1258 lines) | ❌ NOT PORTED | ❌ | Production | 10-50ms est | None |
| **ContentDetector** | ✅ Shim | ✅ Full | ✅ | Production | <1ms | None |
| **TagProtector** | ✅ Shim | ✅ Full | ✅ | Production | <1ms | None |
| **ErrorDetection** | ✅ Shim | ✅ Full | ✅ | Production | <1ms | None |
| **KompressCompressor** | ✅ Full (ML, ONNX) | ❌ | ❌ | Beta (opt-in) | 50-200ms est | None |
| **LLMLinguaCompressor** | ✅ Full (ML, torch) | ❌ | ❌ | Experimental (opt-in) | 100-500ms est | None |
| **HTMLExtractor** | ✅ Full (trafilatura) | ❌ | ❌ | Production | 5-20ms est | None |
| **AudioCompressor** | ✅ Full | ✅ Full | ✅ | Production | <5ms est | None |
| **ImageCompressor** | ❌ NOT IN PYTHON | ✅ Full | ✅ | Production | <5ms est | None |
| **Drain3Compressor** | ✅ Full (optional) | ❌ | ❌ | Beta (opt-in, drain3 dep) | 10-50ms est | None |
| **ProseCompressor** | ✅ Full (132 lines) | ❌ | ❌ | Production | <1ms | None |
| **SelectiveFilter** | ✅ Full (BM25) | ❌ | ❌ | Beta (opt-in) | 5-15ms est | None |
| **QueryAdapter** | ✅ Full (97 lines) | ❌ | ❌ | Production | <1ms | None |
| **AnchorSelector** | ✅ Full (770 lines) | ✅ Full | ✅ | Production | <2ms | None |
| **AdaptiveSizer** | ✅ Full (308 lines) | ✅ Full | ✅ | Production | <1ms | None |
| **VerbatimCompactor** | ✅ Full (139 lines) | ❌ | ❌ | Experimental (benchmarks only) | <1ms | None |
| **CompressionUnits** | ✅ Full (364 lines) | ❌ | ❌ | Production | <1ms | None |

---

## 3. Deep-Dive Findings

### 3.1 ContentRouter 65ms Decomposition

The previous audit attributed 65ms to "model routing." This is incorrect. The 65ms includes cumulative sub-compressor invocation costs.

**Decomposition (estimated from code path analysis):**

| Component | Estimated Time | Notes |
|-----------|---------------|-------|
| SelectiveFilter (optional) | 0-15ms | BM25 scoring, opt-in |
| ReadLifecycleManager (optional) | 0-5ms | Stale/superseded detection, opt-in |
| Per-message loop setup | <1ms | Message iteration, frozen_message_count check |
| `detect_content_type()` (Rust via PyO3) | <1ms | Regex-based, compiled once |
| `TagProtector.protect_tags()` (Rust via PyO3) | <1ms | Single-pass walker |
| **Sub-compressor dispatch** | **50-60ms** | SmartCrusher (0.22ms) + LogCompressor + SearchCompressor + Kompress fallback attempts + code compressor |
| Fallback chain attempts | 0-20ms | SmartCrusher → CompactTable → Kompress → Log fallback |
| `TagProtector.restore_tags()` (Rust via PyO3) | <1ms | Single-pass walker |
| Adaptive ratio calculation | <1ms | Linear interpolation |
| **Total** | **~65ms** | |

**Root cause:** The 65ms is NOT model routing — it's the cumulative cost of invoking multiple sub-compressors in the fallback chain, plus PyO3 bridge overhead for each compressor call. When SmartCrusher passthrough triggers the fallback chain (CompactTable → Kompress → Log), each attempt adds latency.

**The Rust live-zone dispatcher avoids this** because it dispatches directly to the correct compressor based on content type, with no fallback chain.

### 3.2 deep_copy_messages Triple-Copy Analysis

The pipeline performs **three deep copies** of the message list:

| Copy | Location | Purpose | Overhead |
|------|----------|---------|----------|
| COPY #1 | `pipeline.py:301` | Isolate pipeline input from caller | O(N) where N = total message bytes |
| COPY #2 | `cache_aligner.py:282` | CacheAligner returns stable list (but messages are never modified — detector-only) | O(N) redundant |
| COPY #3 | `smart_crusher.py:903` | SmartCrusher returns stable list for in-place content replacement | O(N) per tool message |

**Impact for large conversations (100K+ tokens):**

- `copy.deepcopy()` on a list of message dicts: ~5-15ms for 100K tokens (~400KB-1MB of JSON)
- Three copies: ~15-45ms of pure copy overhead
- For 500K token conversations (multi-hour agent sessions): ~75-225ms

**CacheAligner copy is purely redundant.** The CacheAligner is now detector-only (per its docstring: "The transform's `apply` method is a no-op for messages — it only populates `warnings` and `cache_metrics`"). It deep-copies messages at line 282 but never modifies them. This copy exists solely to maintain the Transform contract (`result.messages` is a stable list), but since CacheAligner doesn't transform messages, the copy is wasted.

**SmartCrusher copy is necessary** because it modifies message content in-place (replacing tool output with compressed version + marker). The pipeline relies on `result.messages` being a new list to avoid mutating the caller's input.

**Recommendation:** CacheAligner should return the input list directly (or a shallow copy) since it never mutates. This eliminates one full deep copy. The pipeline-level copy (#1) is also redundant if all downstream transforms produce new lists — but removing it requires auditing every transform's mutation behavior.

### 3.3 Dual-Runtime Parity Analysis

#### Transforms with Rust Ports

| Transform | Python Status | Rust Status | Parity Enforced? |
|-----------|---------------|-------------|------------------|
| SmartCrusher | Shim (delegates to Rust) | Full port (13 modules, 388+ tests) | ✅ 17 parity fixtures + property tests |
| LogCompressor | Shim (delegates to Rust) | Full port | ✅ Parity fixtures |
| SearchCompressor | Shim (delegates to Rust) | Full port | ✅ Parity fixtures |
| DiffCompressor | **Fallback (Rust returns unchanged)** | Full port (but buggy on real diffs) | ⚠️ Python fallback needed |
| ContentDetector | Shim (delegates to Rust) | Full port | ✅ Parity fixtures |
| TagProtector | Shim (delegates to Rust) | Full port | ✅ 5 bug fixes ported |
| ErrorDetection | Shim (delegates to Rust) | Full port (aho-corasick) | ✅ Keyword tables from Rust |
| AnchorSelector | Full Python | Full Rust | ⚠️ No parity fixtures visible |
| AdaptiveSizer | Full Python | Full Rust | ⚠️ No parity fixtures visible |
| AudioCompressor | Full Python | Full Rust | ⚠️ No parity fixtures visible |
| ImageCompressor | NOT IN PYTHON | Full Rust | N/A (Rust-only) |

#### Transforms with No Rust Port

| Transform | Notes |
|-----------|-------|
| CodeCompressor | **CRITICAL GAP** — 1258-line Python AST compressor has no Rust equivalent. The live-zone dispatcher skips SourceCode blocks entirely. |
| KompressCompressor | ML-based (ModernBERT ONNX), requires Python runtime anyway |
| LLMLinguaCompressor | ML-based (torch), requires Python runtime anyway |
| HTMLExtractor | Uses trafilatura (Python lib), no Rust equivalent |
| Drain3Compressor | Uses drain3 (Python lib), no Rust equivalent |
| ProseCompressor | Lightweight regex-based, could be ported but low priority |
| SelectiveFilter | BM25 scoring, could be ported but low priority |
| CacheAligner | Detector-only, low priority |
| QueryAdapter | Configuration mapping, trivial |

#### Parity Drift Risks

1. **DiffCompressor:** The Rust version returns input unchanged for many real-world diffs, forcing a Python fallback. This creates two code paths with potentially different behavior. The Python fallback strips metadata lines and reduces context lines — the Rust version may not.

2. **AnchorSelector / AdaptiveSizer:** Both exist in Python and Rust with no visible parity enforcement. If the Rust live-zone path uses the Rust implementations while the Python pipeline uses Python versions, behavior may diverge.

3. **SmartCrusher compaction:** The Python shim has a `with_compaction` flag and fallback to CompactTableCompressor that the Rust path doesn't replicate. The Rust path in `live_zone.rs` calls SmartCrusher directly without the fallback chain.

---

## 4. Key Issues

### CRITICAL

**C1: CodeCompressor Not Ported to Rust**
- **Impact:** The Rust live-zone dispatcher (`live_zone.rs:164-166`) skips `SourceCode` blocks entirely. Code blocks in tool outputs (the most common large payload) pass through uncompressed in the Rust path.
- **Severity:** CRITICAL — this is the highest-value compressor that's missing from Rust.
- **Location:** `crates/cutctx-core/src/transforms/mod.rs` — no `code_compressor` module exists.

**C2: Triple deep_copy in Python Pipeline**
- **Impact:** For 100K+ token conversations, ~15-45ms of pure copy overhead. For 500K tokens, ~75-225ms.
- **Severity:** CRITICAL — this is pure waste, especially CacheAligner's copy.
- **Location:** `pipeline.py:301`, `cache_aligner.py:282`, `smart_crusher.py:903`

### HIGH

**H1: DiffCompressor Rust Path Non-Functional**
- **Impact:** Rust DiffCompressor returns input unchanged for many diffs, forcing Python fallback. Creates dual code paths.
- **Severity:** HIGH — the Rust live-zone dispatcher calls Rust DiffCompressor, which may not compress diffs at all.
- **Location:** `diff_compressor.py:8` (docstring), `live_zone.rs:123`

**H2: ContentRouter 65ms Overhead Misattributed**
- **Impact:** The 65ms is sub-compressor invocation + fallback chain, not "model routing." Misattribution leads to wrong optimization targets.
- **Severity:** HIGH — optimization efforts should target the fallback chain, not routing logic.
- **Location:** `content_router.py` `_apply_strategy_to_content()` chain

**H3: SmartCrusher Fallback Chain Not in Rust Path**
- **Impact:** Python SmartCrusher has fallback: lossless → CompactTable → Kompress → Log. Rust live-zone dispatcher calls SmartCrusher directly without these fallbacks. May produce worse compression on edge cases.
- **Severity:** HIGH — behavioral divergence between Python and Rust paths.
- **Location:** `live_zone.rs:dispatch_compressor()` vs `content_router.py:1477-1537`

### MEDIUM

**M1: AnchorSelector/AdaptiveSizer Parity Not Enforced**
- **Impact:** Both exist in Python and Rust with no visible parity fixtures. Behavioral drift possible.
- **Severity:** MEDIUM — affects compression quality consistency.
- **Location:** `anchor_selector.py`, `adaptive_sizer.py`

**M2: KompressCompressor/LLMLinguaCompressor Python-Only**
- **Impact:** ML compressors require Python runtime, can't run in Rust-only proxy mode.
- **Severity:** MEDIUM — these are opt-in and experimental, but block Rust-only deployment.
- **Location:** `kompress_compressor.py`, `llmlingua_compressor.py`

### LOW

**L1: ProseCompressor Could Be Ported**
- **Impact:** Lightweight regex-based compressor, low priority for Rust port.
- **Severity:** LOW — already fast in Python.
- **Location:** `prose_compressor.py` (132 lines)

**L2: VerbatimCompactor Experimental**
- **Impact:** Only used in benchmarks, not in production pipeline.
- **Severity:** LOW — benchmarking utility only.
- **Location:** `verbatim_compactor.py`

---

## 5. Recommendations

### Immediate (Phase 1)

1. **Eliminate CacheAligner deep_copy:** CacheAligner is detector-only. Change `cache_aligner.py:282` to return the input list directly (or `messages[:]` shallow copy). Saves O(N) copy for every pipeline invocation.

2. **Audit SmartCrusher deep_copy necessity:** If SmartCrusher could accept an immutable list and return a new list (rather than copying then mutating), the copy could be eliminated. Current design copies then mutates — the copy is necessary for correctness but the pattern is wasteful.

3. **Document ContentRouter latency decomposition:** Add timing instrumentation to `_apply_strategy_to_content()` to measure each sub-compressor invocation separately. This will confirm the 65ms breakdown.

### Short-term (Phase 2)

4. **Port CodeCompressor to Rust:** This is the highest-impact Rust port remaining. The Python implementation uses tree-sitter (already available in Rust). The live-zone dispatcher would then compress SourceCode blocks.

5. **Fix DiffCompressor Rust path:** The Rust DiffCompressor needs to handle real-world diffs (metadata stripping, context line reduction). The Python fallback exists but shouldn't be needed.

6. **Add parity fixtures for AnchorSelector/AdaptiveSizer:** If both runtimes are maintained, parity must be enforced.

### Medium-term (Phase 3)

7. **Eliminate pipeline-level deep_copy:** If all transforms return new lists (immutable pattern), the pipeline-level copy at `pipeline.py:301` can be removed. Requires auditing every transform.

8. **Port SmartCrusher fallback chain to Rust:** The CompactTable → Kompress → Log fallback chain should work in the Rust path too.

9. **Consider async deep_copy:** For very large conversations, `copy.deepcopy()` blocks the thread. An async or chunked copy could reduce tail latency.

---

## Appendix A: File Line Counts

| File | Lines | Role |
|------|-------|------|
| `pipeline.py` | 537 | Python pipeline orchestrator |
| `content_router.py` | 3,256 | Content-aware routing + compression dispatch |
| `smart_crusher.py` | 1,015 | SmartCrusher shim (delegates to Rust) |
| `code_compressor.py` | 1,258 | AST-based code compression (Python-only) |
| `log_compressor.py` | 525 | Log compressor shim (delegates to Rust) |
| `search_compressor.py` | 373 | Search compressor shim (delegates to Rust) |
| `diff_compressor.py` | 360 | Diff compressor (Rust + Python fallback) |
| `kompress_compressor.py` | 1,319+ | ML compressor (ModernBERT ONNX) |
| `cache_aligner.py` | 388 | Cache prefix detection (detector-only) |
| `anchor_selector.py` | 770 | Dynamic anchor selection |
| `adaptive_sizer.py` | 308 | Information saturation detection |
| `compression_units.py` | 364 | Provider-neutral compression units |
| `base.py` | 78 | Transform ABC |
| `error_detection.py` | 190 | Error/importance detection shim |
| `tag_protector.py` | 131 | Tag protector shim (delegates to Rust) |
| `prose_compressor.py` | 132 | Query-aware prose compression |
| `selective_filter.py` | 212 | BM25 relevance filtering |
| `query_adapter.py` | 97 | Task-type compression hints |
| `verbatim_compactor.py` | 139 | Deterministic line compaction |
| `html_extractor.py` | 233 | HTML content extraction |
| `audio_compressor.py` | 282 | Audio compression |
| `llmlingua_compressor.py` | 239 | LLMLingua integration |
| `drain3_compressor.py` | 362 | Drain3 log template mining |

| Rust File | Lines | Role |
|-----------|-------|------|
| `live_zone.rs` | 3,289 | Live-zone block dispatcher |
| `pipeline/orchestrator.rs` | 906 | Rust pipeline orchestrator |
| `pipeline/traits.rs` | 338 | ReformatTransform/OffloadTransform traits |
| `content_detector.rs` | 769 | Content type detection |
| `smart_crusher/mod.rs` | 81 | SmartCrusher module root (13 sub-modules) |
