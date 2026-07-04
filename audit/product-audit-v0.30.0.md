# Cutctx Product Audit: Capabilities vs Claims

**Version:** v0.30.0 (installed v0.30.1)
**Date:** 2026-07-04
**Scope:** Compression engine, claims verification, benchmarks, buyer journey, architecture

---

## 1. Executive Summary

Cutctx's compression engine is real and effective — the ContentRouter pipeline achieves **78% compression with 0.999 F1** on structured tool output data, and the architecture is well-engineered (Rust core with Python orchestration, clean OSS/EE license boundary, 8K+ tests). **However, 4 critical marketing gaps undermine buyer trust:** the headline "87% Avg Token Reduction" is misleading (median is 4.8%, mean is 11.3%), the most publicized "60 second" setup takes 7-12 minutes, the enterprise-tier LLM Firewall advertises features that are disabled or non-functional, and ROI "case studies" are unfilled templates. Additionally, the bare `pip install cutctx-ai` produces a working install that does nothing useful until extras are added, creating an immediate disappointment for first-time users.

---

## 2. Critical Findings

### CRITICAL-1: "87% Avg Token Reduction" is 7-18x exaggeration

| Aspect | Detail |
|---|---|
| **Claim** | `wiki/index.md:22-25` — Hero stat card: "87% / Avg Token Reduction". No qualification, no asterisk, no link to methodology. |
| **Source of 87%** | A single test: 100 production log entries with a FATAL error at position 67 (`wiki/index.md:287-294`, `wiki/benchmarks.md:107-118`). **N=1, not an average.** |
| **Real production data** | 50,000+ sessions, 250+ instances (`wiki/benchmarks.md:47-56`): P25 **4.8%**, Median **4.8%**, P75 **6.9%**, Mean **11.3%** |
| **Max exaggeration** | 87% is **18× the median**, **7.7× the mean** |
| **Internal admission** | `artifacts/pitchdeck.md:293` — explicitly warns *"do not make universal compression-ratio claims"* and notes median is 4.8%. The pitchdeck is honest; the wiki homepage is not. |
| **Honest framing** | Median ~5%, mean ~11% overall. Heavy tool-use users see 40-80%. Best-case structured data (JSON arrays, logs) hits 90%+ on eligible content only. |

### CRITICAL-2: "1.4 billion tokens saved" is unverifiable

The headline fleet-wide metric appearing in `wiki/benchmarks.md:5-7` and 6+ marketing files is flagged **"unverifiable — no aggregated telemetry data"** in the internal `docs/CHANGE_LOG.md:82`. The telemetry infrastructure exists (`cutctx/telemetry/`) but there is no way to independently confirm this number. The data is from v0.5.17-era (current is v0.30.0).

### HIGH-3: LLM Firewall advertises non-functional features

| Claim | File | Reality |
|---|---|---|
| "27 regex patterns" | `README.md:281`, `PRODUCT_GUIDE.md:450`, `ENTERPRISE.md:135` | **24 patterns** (7 injection + 4 jailbreak + 11 PII + 2 exfiltration). Off by 3. |
| "Streaming redactor" | Same three docs | **Exists but gated on firewall being enabled** (off by default). Entire pipeline disabled unless user explicitly opts in. |
| "ML classifier" | `ENTERPRISE.md:135` — listed as "Available" | **Dead code.** `MLInjectionClassifier` defined in `firewall_ml.py` but no `.onnx` model file ships (directory missing), returns `0.0` for all inputs, and is **not integrated** into `FirewallScanner` (no call site). |

**Impact on enterprise buyers:** The Enterprise tier explicitly claims an ML classifier as part of the deliverable. It is non-functional in every practical sense.

### HIGH-4: ROI "case studies" are unfilled templates

Three named ROI cases in `PRODUCT_GUIDE.md:656-671` (493%/680%/471%) share the same structure and language as `marketing/case-study-template.md`, which is a template with `[Company Name]` placeholders. The pitchdeck (`pitchdeck.md:173-175`) presents them as real customer data. They are sales illustrations, not verified case studies.

### HIGH-5: RBAC claim false — disabled at mount time

`README.md:286` claims "RBAC — wired into ALL admin endpoints." In reality:
- **41 of 79 admin endpoints** (52%) are missing at least one of admin_auth/rbac_permission/entitlement
- 4 endpoints have **no admin auth at all** (only `require_entitlement("ccr")`)
- The production mount (`server.py:4545`) passes `require_rbac_permission=None`, making RBAC a **no-op for the entire `/admin/*` surface**
- Loopback bypass still exists for telemetry endpoints (`/livez`, `/readyz`, `/metrics`)

### HIGH-6: Buyer journey takes 7-12 minutes, not "60 seconds"

| Advertised | Actual | Issue |
|---|---|---|
| `pip install cutctx-ai` → works | Bare install: only `cutctx bench` works. Proxy, wrap, savings, MCP all fail without `[proxy]` extra. | First-minute devaluation |
| "Get started in 60 seconds" (README) | E2E to first value: **7-12 minutes** (install 3-8min, API key 1min, proxy start 1min) | 10x exaggeration |
| `cutctx bench` verifies compression | Runs **inline dummies**, not real production compressors. Reports fake ratios. | Misleading UX |
| Savings HTML report | Chart uses `Math.random()`, sessions table hardcoded. Only stat cards are real. | Demo credibility issue |
| `cutctx init`/`cutctx setup` | Not in README "Get started" section. Users follow `cutctx wrap` instead, which is session-scoped. | Missing onboarding path |

---

## 3. Claims Verification Table

| # | Claim (file:line) | Reality | Verdict | Severity |
|---|---|---|---|---|
| 1 | "87% Avg Token Reduction" — `wiki/index.md:22-25` | Median 4.8%, mean 11.3%. 87% is N=1 test. | **MISLEADING** | CRITICAL |
| 2 | "1.4 billion tokens saved" — `wiki/benchmarks.md:5-7` + 6 files | Unverifiable per internal audit (`CHANGE_LOG.md:82`). v0.5.17-era. | **UNVERIFIABLE** | CRITICAL |
| 3 | "LLM Firewall: 27 regex + streaming redactor + ML classifier" — `README.md:281`, etc. | 24 patterns (not 27). Streaming gated on off-by-default firewall. ML classifier dead code, no model file, not integrated. | **INACCURATE** | HIGH |
| 4 | ROI "case studies" (493%/680%/471%) — `PRODUCT_GUIDE.md:656-671` | Unfilled template `[Company Name]` placeholders. | **TEMPLATES** | HIGH |
| 5 | "RBAC wired into ALL admin endpoints" — `README.md:286` | 41/79 endpoints missing guards. Production mount passes `require_rbac_permission=None` — RBAC is no-op. | **INACCURATE** | HIGH |
| 6 | "60 seconds" setup — `README.md:92` | Actual E2E: 7-12 minutes. Bare install worthless without `[proxy]` extra. | **OVERSTATED** | HIGH |
| 7 | "CodeCompressor 60-80%" — `PRODUCT_GUIDE.md:106` | Off by default. 3 protection gates block >90% real code. LIMITATIONS.md calls it "Passthrough." Own benchmark: 47%. | **MISLEADING** | MEDIUM |
| 8 | "100+ LLM Providers" — `wiki/index.md:36` | 6 explicit implementations + LiteLLM wrapper. Stat card unqualified. Rest of docs qualify "via LiteLLM." | **OVERSTATED** | MEDIUM |
| 9 | "50,000+ sessions, 250+ instances" — `wiki/benchmarks.md:34` | v0.5.17-era data, not v0.30.0. | **STALE** | MEDIUM |
| 10 | Agent compat matrix — `README.md:162-170` | Omits Windsurf, Zed, opencode listed in PRODUCT_GUIDE.md. | **INCOMPLETE** | LOW |
| 11 | "1,000+ tests" — `PRODUCT_GUIDE.md:746` | Actual: 8,137 Python + 1,401 Rust = ~9,538. | **UNDERSTATED** | Info |

---

## 4. Architecture Truth Map

### Rust vs Python Split

```
User Request
     │
     ▼
┌────────────────────────────────────────────────────────┐
│  Python Proxy (FastAPI, 6,901 LOC)                     │
│  ───────────────────────────────────────────────       │
│  CircuitBreaker → ToolResultInterceptor (opt-in)       │
│  → CacheAligner → ContentRouter                        │
│  │              │                                      │
│  │              ▼                                      │
│  │   Routes by content type:                           │
│  │   CODE_AWARE → CodeCompressor (Python+tree-sitter)  │
│  │   JSON_ARRAY → SmartCrusher (★RUST) → CompactTable  │
│  │                     → Kompress → LogCompressor       │
│  │   SEARCH     → SearchCompressor (★RUST)             │
│  │   BUILD_LOG  → LogCompressor (★RUST)                │
│  │   GIT_DIFF   → DiffCompressor (★RUST + Python fbk)  │
│  │   HTML       → HTMLExtractor (Python)               │
│  │   TEXT       → Kompress (ONNX ML, Python)           │
│  │              │                                      │
│  └──────────────┼──────────────────────────────────────┘
│                 │ import cutctx._core (PyO3)
│                 ▼
│  ┌─────────────────────────────────────────────┐
│  │ Rust Core (crates/cutctx-core)              │
│  │ SmartCrusher, LogCompressor, SearchCompressor│
│  │ DiffCompressor, ImageCompressor,             │
│  │ tag_protector, content_detection,            │
│  │ CCR stores, relevance (BM25/hybrid),         │
│  │ stack_graph, licensing, antidebug, tokenizer │
│  └─────────────────────────────────────────────┘
```

**Key architectural facts:**
- **Rust core is REQUIRED** — exit 78 (EX_CONFIG) if `cutctx._core` can't import. Opt-out `CUTCTX_REQUIRE_RUST_CORE=false` → degraded Python-only mode. No graceful fallback for core compressors (post-May 2026 audit fix).
- **Python does**: pipeline orchestration, content routing, proxy server, CLI, MCP, dashboard, integrations, Kompress/LLMLingua/Drain3 ML, memory system, all EE features
- **15+ PyO3 bindings** bridge Rust to Python as `cutctx._core`
- **Pipeline flow**: ContentRouter detects type (Rust magika chain) → routes to optimal compressor → fallback chain on each strategy

### Integration Architecture (corrected)

| Integration | Compression Mode | HTTP Client? |
|---|---|---|
| LangChain | In-process (wraps BaseChatModel) | No |
| LlamaIndex | In-process (post-processor) | No |
| Agno | In-process (model wrapper + hooks) | No |
| Strands | In-process (hook provider) | No |
| ASGI middleware | In-process (default) | **Opt-in cloud mode** → `pitchtoship.com/v1/saas/compress` (`asgi.py:210-243`) |
| LiteLLM callback | In-process (default) | **Opt-in cloud mode** → same endpoint (`litellm_callback.py:145-178`) |

### License Boundary

- **`cutctx/`** — Apache-2.0 (compression engine, proxy, CLI, integrations, dashboard, MCP, SDKs, base memory)
- **`cutctx_ee/`** — LicenseRef-Cutctx-Commercial (billing, entitlements, RBAC, SSO, SCIM, audit hash-chain, fleet, retention, seats, org hierarchy, team memory)
- Clean import-gated boundary with Apache-side shims
- **No copyleft dependencies** — all deps MIT/Apache-2.0/BSD-3

---

## 5. Compression Benchmarks (v0.30.1, real run)

**Dataset:** `tool_outputs` (8 samples, structured agent tool output data)
**Command:** `cutctx evals benchmark -d tool_outputs --n 10`
**Seed:** 42

| Compressor | Ratio | F1 | Info Recall | Notes |
|---|---|---|---|---|
| **ContentRouter** (default) | **78.2%** | 0.999 | 1.000 | What users get by default |
| SmartCrusher | 79.1% | 1.000 | 1.000 | Perfect retention on JSON |
| Log | 88.3% | 0.882 | 0.875 | Highest ratio, some info loss |
| Search | 79.3% | 0.862 | 0.817 | Lower recall |
| Diff | 100.0% | 1.000 | 1.000 | No diffs in dataset |
| Kompress | 78.8% | 0.999 | 1.000 | Strong ML fallback |
| Code | 80.5% | 0.999 | 1.000 | On code-containing outputs |

**Takeaway:** ContentRouter achieves 78.2% compression on structured tool output with 0.999 F1. The compression engine works well on its target data. **The marketing problem is framing** — the 87% headline stands in for this benchmark data but is presented as a general average.

---

## 6. Buyer Journey Friction (Prioritized)

| # | Friction | Claim | Reality | Severity |
|---|---|---|---|---|
| 1 | Bare install produces zero value | `pip install cutctx-ai` (README) | Only `cutctx bench` works. Proxy/wrap/savings/MCP fail without `[proxy]` extra. | CRITICAL |
| 2 | "60 seconds" is misleading | "Get started in 60 seconds" (README) | E2E first value: 7-12 minutes. Install 3-8min alone. | CRITICAL |
| 3 | `cutctx bench` tests fake compressors | Shows compression works | Inline dummy code, not real SmartCrusher/Kompress. Reports are misleading. | HIGH |
| 4 | Savings HTML chart is fake data | Savings report | Chart uses `Math.random()`. Sessions table hardcoded. Only stat cards real. | HIGH |
| 5 | `cutctx init`/`setup` not in README | "Get started" mentions only `wrap` | Users miss durable install path. Persistent proxy started without consent. | MEDIUM |
| 6 | Dashboard loopback-only | Shareable dashboard | `_require_local_admin_auth` — can't demo remotely without config. | MEDIUM |
| 7 | `cutctx perf` not in `--help` | Listed as 60-second step (README) | Not discoverable via `cutctx --help`. Hidden in lazy-loaded group. | MEDIUM |
| 8 | Many CLI flags lack env vars | Configurable proxy | `--workers`, `--budget`, `--log-file`, etc. are CLI-only. Can't use `.env`. | MEDIUM |
| 9 | Rust core hard fail on sdist install | `pip install cutctx-ai` works | Exit 78 if no prebuilt wheel and no Rust toolchain. | MEDIUM |
| 10 | Zero-data UX inconsistent | Savings shows useful empty state | Says "Run `cutctx wrap claude`" — useless if user doesn't have Claude Code. | LOW |

---

## 7. Recommendations

### Immediate Fixes (credibility-critical)

| # | Fix | Target | Effort |
|---|---|---|---|
| 1 | Add asterisk/qualification to "87% Avg Token Reduction" stat card — link to benchmarks page showing median 4.8% | `wiki/index.md:22-25` | 5 min |
| 2 | Either make `pip install cutctx-ai` include `[proxy]` deps by default, or print a clear error directing to the extra | `pyproject.toml`, `cli/main.py` | 1-2 days |
| 3 | Fix the LLM Firewall claims: correct "27" to "24", document "off by default + requires opt-in", remove "ML classifier Available" from enterprise docs | `README.md:281`, `PRODUCT_GUIDE.md:450`, `ENTERPRISE.md:135` | 1 day |
| 4 | Replace `Math.random()` chart and hardcoded sessions table with real data in savings HTML report | `cutctx/cli/savings.py:541,585` | 1 day |
| 5 | Either remove the three ROI "case studies" or label them as "illustrative examples" not customer data | `PRODUCT_GUIDE.md:656-671`, `pitchdeck.md:173-175` | 1 day |
| 6 | Fix RBAC production mount: pass real `require_rbac_permission` instead of `None` | `cutctx/proxy/server.py:4545` | 1 day |

### Near-term Improvements

| # | Fix | Effort |
|---|---|---|
| 7 | Add `cutctx init`/`cutctx setup` to README "Get started" section | 1 hour |
| 8 | Replace `cutctx bench` with real compressors (or rename to `cutctx bench-quick` and add `cutctx bench-real`) | 2-3 days |
| 9 | Add env var equivalents for CLI-only flags (`CUTCTX_WORKERS`, `CUTCTX_BUDGET`, etc.) | 1-2 days |
| 10 | Remove or re-verify "1.4 billion tokens" claim — if telemetry can reproduce it, document methodology; if not, remove | Varies |
| 11 | Add "100+ via LiteLLM" qualifier to stat card | 5 min |
| 12 | Update fleet telemetry to current v0.30.0 data or remove stale numbers | 1 hour |

### Architecture & Engineering

| # | Fix | Effort |
|---|---|---|
| 13 | Wire ML classifier model or remove the dead code path | 2-3 days |
| 14 | Enable firewall by default (or remove the feature from enterprise marketing until it's on) | 1 day |
| 15 | Complete CodeCompressor safety gate documentation so users understand when it fires vs passes through | 1 day |

---

## 8. Methodology

All findings were validated by:
- **Source code reading** — each claim traced to its implementing code and compared against documentation
- **Benchmark execution** — `cutctx evals benchmark` run on v0.30.1 with `tool_outputs` dataset
- **CLI testing** — each command invoked to verify help output, argument parsing, and execution path
- **Architecture analysis** — Rust vs Python boundary, pipeline flow, feature gates, license boundaries, integration patterns
- **Cross-reference** — each marketing claim cross-checked against internal audit docs (`SOC2_CONTROLS.md`, `RELEASE_REPORT.md`, `CHANGE_LOG.md`)

### Files referenced

Full file paths available in `.slim/deepwork/product-audit.md` and individual verification task outputs.

---

## Appendix: Key File References

| File | Purpose |
|---|---|
| `wiki/index.md:22-25` | "87% Avg Token Reduction" stat card |
| `wiki/benchmarks.md:47-56` | Real production compression data (4.8% median) |
| `wiki/benchmarks.md:107-118` | Source of 87.6% number (N=1 test) |
| `artifacts/pitchdeck.md:293` | Internal warning against universal claims |
| `README.md:281` | LLM Firewall claim |
| `PRODUCT_GUIDE.md:450-451` | LLM Firewall claim |
| `ENTERPRISE.md:135` | LLM Firewall claim |
| `cutctx/security/firewall.py:62` | Firewall default `enabled=False` |
| `cutctx/security/firewall_ml.py` | ML classifier — no model, not integrated |
| `docs/security/SOC2_CONTROLS.md:26` | Internal honesty about firewall state |
| `PRODUCT_GUIDE.md:656-671` | ROI case studies |
| `marketing/case-study-template.md` | Template with `[Company Name]` placeholders |
| `README.md:286` | RBAC claim |
| `cutctx/proxy/server.py:4545` | `require_rbac_permission=None` production mount |
| `cutctx/proxy/server.py:281-349` | Rust core `_check_rust_core()` exit 78 |
| `cutctx/cli/bench.py` | `cutctx bench` — inline dummy compressors |
| `cutctx/cli/savings.py:541,585` | Fake chart data in HTML report |
| `crates/cutctx-py/src/lib.rs` | PyO3 bindings |
| `crates/cutctx-core/src/lib.rs` | Rust core entry point |
| `cutctx/transforms/content_router.py:443-592` | Feature gate defaults |
| `pyproject.toml:51-66` | Base dependencies (no proxy extra) |
| `pyproject.toml:68-303` | Optional extras |
