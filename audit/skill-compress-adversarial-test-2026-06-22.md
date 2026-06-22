# CutCtx Adversarial Test Report
**Date:** 2026-06-22  
**Package tested:** `headroom-ai` v0.27.0  
**Tested against:** SKILL.md claims for `cutctx:compress`

---

## Executive Summary

The cutctx SKILL.md has **several materially wrong claims** and some **misleading framings**, alongside genuinely working functionality. The core compression algorithms are real and functional. The CLI interface described does not match reality. Compression ratios are often accurate but can significantly overshoot or undershoot claims depending on data characteristics.

---

## Claim-by-Claim Verdict

### 1. Installation

| Claim | Result | Verdict |
|-------|--------|---------|
| `pip install headroom-ai` installs the tool | ✅ Installs package | PASS |
| `pip install "headroom-ai[all]"` works | ❌ Disk error in sandbox, but proxy deps install fine via `[proxy]` | PARTIAL |
| CLI binary is `cutctx` | ❌ Binary installed is `headroom`, not `cutctx` | **FAIL** |
| `cutctx-ai` is available on PyPI | ❌ `pip install cutctx-ai` → "No matching distribution found" | **FAIL** |

**Finding:** When installing from PyPI via `pip install headroom-ai`, only the `headroom` binary is installed. The `cutctx` binary only exists inside the project's own `.venv` (a Python wrapper calling `headroom.cli:main`) and as a macOS ARM64 compiled Rust binary in `target/debug/`. The `cutctx-ai` package name referenced in `pyproject.toml` is not on PyPI. **Every example in the SKILL.md uses `cutctx <command>` but the real CLI is `headroom <command>`.**

---

### 2. CLI Commands

| Claim | Result | Verdict |
|-------|--------|---------|
| `echo "text" \| cutctx compress` | ❌ `headroom compress` → "No such command 'compress'" | **FAIL** |
| `cutctx compress < file.txt` | ❌ Same — no compress subcommand | **FAIL** |
| `cutctx stats` | ❌ `headroom stats` → "No such command 'stats'" | **FAIL** |
| `cutctx proxy --port 8787` | ✅ `headroom proxy --port 8787` works | PASS (wrong name) |
| `cutctx retrieve <hash>` | ❌ `headroom retrieve` → "No such command 'retrieve'" | **FAIL** |

**Finding:** Of the 5 documented CLI commands, only the proxy command works (under the correct binary name). The `compress`, `stats`, and `retrieve` subcommands do not exist in the CLI. The correct equivalent to `stats` is the web endpoint `GET /stats` on the running proxy, or `headroom memory stats` (for memory only). Retrieval is only possible via Python API or SQLite directly.

---

### 3. Auto-Start Proxy

| Claim | Result | Verdict |
|-------|--------|---------|
| "CutCtx proxy starts automatically when this plugin loads" | ❌ No auto-start. Proxy requires manual `headroom proxy` invocation | **FAIL** |
| Proxy requires extra deps beyond base `pip install headroom-ai` | ❌ Yes: needs `fastapi`, `uvicorn`, `httpx[http2]`, `openai`, `socksio` — install with `pip install headroom-ai[proxy]` | MISLEADING |
| `curl http://127.0.0.1:8787/livez` works once proxy is running | ✅ Returns `{"status":"healthy","alive":true,...}` | PASS |

**Finding:** The auto-start claim is false — the proxy is not started by loading the skill. Additionally, `pip install headroom-ai` alone fails to start the proxy (`No module named 'fastapi'`). You must install `headroom-ai[proxy]` separately.

---

### 4. Compression Algorithms — Existence

All 5 algorithms exist as real Python classes:

| Algorithm | Class | Module |
|-----------|-------|--------|
| SmartCrusher | `SmartCrusher` | `headroom.transforms.smart_crusher` |
| CodeCompressor | `CodeAwareCompressor` + `compress_code()` | `headroom.transforms.code_compressor` |
| DiffCompressor | `DiffCompressor` | `headroom.transforms.diff_compressor` |
| LogCompressor | `LogCompressor` | `headroom.transforms.log_compressor` |
| SearchCompressor | `SearchCompressor` | `headroom.transforms.search_compressor` |

**Finding:** The naming in SKILL.md is mostly accurate (CodeCompressor is actually `CodeAwareCompressor`). All 5 are real.

---

### 5. Compression Ratios — Measured vs. Claimed

All measurements use actual token counts via `headroom.compress()`.

#### SmartCrusher — JSON/Structured Data (Claimed: 60–90%)
| Test | Input Tokens | Output Tokens | Actual Savings |
|------|-------------|--------------|---------------|
| 100-user JSON, uniform structure | 7,739 | 2,794 | **63.9%** ✅ |
| 100-user JSON, chars only | 35,509 → 16,734 chars | — | 52.9% ⚠️ |
| 100-item API response | 16,390 → 6,645 chars | — | 59.4% ⚠️ |
| Single JSON object | 56 chars | 51 chars | 8.9% (just whitespace) |
| Plain prose (no structure) | 0% savings | passes through unchanged | ✅ correct behavior |

**Verdict:** Savings are **real but frequently below the claimed 60% floor** on character count. On token count with a proper conversation (prior assistant message), hits **~64%**, which is at the low end of the claimed range. The algorithm converts JSON arrays to a compact CSV-like format.

#### CodeCompressor (Claimed: 40–70%)
**Not testable without extra install:** requires `pip install headroom-ai[code]` (tree-sitter). The base `headroom-ai` install does not include this. The `compress_code()` function exists but throws an error on invocation without tree-sitter. SKILL.md does not mention this prerequisite.

**Verdict:** ❌ **Not functional out of the box.** Requires undisclosed extra dependency.

#### DiffCompressor (Claimed: 70–95%)
| Test | Input | Output | Savings |
|------|-------|--------|---------|
| Small realistic diff (1 file, 7KB) | 7,092 chars | 7,035 chars | **0.8%** ❌ |
| 50-file repetitive diff (18KB) | 17,829 chars | 6,604 chars | **63.0%** ⚠️ |

**Verdict:** Savings are **highly dependent on repetition**. On a real-world single-file diff (the most common case), savings were under 1%. The claimed 70–95% only materializes with many nearly-identical hunks across many files. The "70–95%" claim is the best case, not the typical case.

#### LogCompressor (Claimed: 80–95%)
| Test | Input | Output | Savings |
|------|-------|--------|---------|
| 200 identical stack traces (111KB) | 5,801 tokens | 679 tokens | **88.3%** ✅ |
| 100 identical error lines (tokens) | 5,801 → 679 | — | **88.3%** ✅ |

**Verdict:** Claim is accurate for **highly repetitive logs** (same error repeated). Works well. This is the algorithm that performs closest to its advertised range.

#### SearchCompressor (Claimed: 50–80%)
| Test | Input | Output | Savings |
|------|-------|--------|---------|
| 50 repetitive search results | 21,939 chars | 224 chars | **99.0%** ⚠️ |
| 30 identical grep result blocks | 13,109 chars | 613 chars | **95.3%** ⚠️ |
| 20 unique grep lines | 878 chars | 550 chars | 37.4% ⚠️ |
| 10 unique/varied search results | 1,610 chars | 1,610 chars | **0%** ❌ |

**Verdict:** The claim of 50–80% is **both an understatement and an overstatement depending on data.** For repetitive grep output it achieves 95%+, far above the claimed ceiling. For unique results it achieves 0%. The algorithm works by grouping identical patterns — it's a **deduplication engine**, not a general semantic compressor.

**⚠️ Lossy compression concern:** SearchCompressor's output for highly repetitive inputs shows only a few representative lines plus `[N matches compressed. Retrieve more: hash=...]`. The truncated lines are stored in a SQLite CCR store with a **30-minute TTL (1800 seconds)**. After TTL expiry, the original content is unrecoverable. For agentic workflows that might revisit compressed context hours later, this is a silent data loss risk.

---

### 6. CCR (Compressed Content Retrieval)

| Claim | Result | Verdict |
|-------|--------|---------|
| `cutctx retrieve <hash>` CLI command | ❌ Does not exist | **FAIL** |
| Content stored for retrieval | ✅ SQLite at `~/.headroom/ccr_store.db` | PASS |
| Content recoverable via Python API | ✅ `SmartCrusher.ccr_get(hash)` returns None for invalid hashes, original for valid | PASS |
| SearchCompressor stores originals | ✅ Verified via DB query | PASS |
| TTL on stored content | ⚠️ 1800 seconds (30 min) — not mentioned in SKILL.md | UNDISCLOSED |

---

### 7. Proxy Endpoints

| Claimed Endpoint | Actual Result |
|-----------------|---------------|
| `GET /livez` | ✅ `{"status":"healthy","alive":true,"version":"0.27.0",...}` |
| `GET /stats` (implied by `cutctx stats`) | ✅ Works, but only via HTTP on running proxy, not CLI |
| `GET /readyz` | ✅ Returns detailed health check (reports unhealthy without valid API key) |
| `GET /metrics` | ✅ Prometheus metrics exposed |

---

### 8. Documentation Links

| Link | Status |
|------|--------|
| `https://cutctx.dev/docs` | 403 Forbidden (blocked by network allowlist in this env) |
| `https://github.com/AryanSingh/cutcxt` | **404 Not Found** — note typo in SKILL.md: "cutcxt" vs "cutctx" |

---

## Summary Table

| Claim Category | Status |
|---------------|--------|
| CLI binary name (`cutctx`) | ❌ Wrong — binary is `headroom` |
| `cutctx compress` command | ❌ Does not exist |
| `cutctx stats` command | ❌ Does not exist |
| `cutctx retrieve` command | ❌ Does not exist |
| `cutctx proxy` command | ✅ Works (as `headroom proxy`) |
| Proxy auto-start | ❌ False — manual only |
| Proxy extra deps required | ❌ Not disclosed |
| SmartCrusher savings (60–90%) | ⚠️ ~64% on tokens, can undershoot on chars |
| CodeCompressor savings (40–70%) | ❌ Requires undisclosed `[code]` extra |
| DiffCompressor savings (70–95%) | ⚠️ ~63% best case, <1% single-file diffs |
| LogCompressor savings (80–95%) | ✅ ~88% on repetitive logs |
| SearchCompressor savings (50–80%) | ⚠️ 0–99% depending on repetition; range claim is misleading |
| CCR retrieval via CLI | ❌ Does not exist |
| CCR retrieval via Python API | ✅ Works |
| CCR TTL disclosure | ❌ 30-min TTL undisclosed |
| GitHub link | ❌ Typo → 404 |

---

## Recommendations

1. **Rename all examples** from `cutctx` to `headroom` until the cutctx-ai package is published to PyPI.
2. **Remove or rewrite the CLI compress/stats/retrieve examples** — these commands do not exist. The Python API (`headroom.compress()`) is the correct interface for direct compression.
3. **Clarify proxy is not auto-started** and that `pip install headroom-ai[proxy]` is required.
4. **Disclose CodeCompressor requires `headroom-ai[code]`** (tree-sitter).
5. **Correct the DiffCompressor claim** — 70–95% is only realistic for large repetitive multi-file diffs. Single-file diffs get <1%.
6. **Add TTL warning to SearchCompressor** — 30-minute expiry on CCR hashes is a silent data loss risk in long-running agents.
7. **Fix GitHub link typo**: `AryanSingh/cutcxt` → `AryanSingh/cutctx`.
