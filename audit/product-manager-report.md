# Cutctx — Product Manager Audit Report

**Product:** Cutctx (formerly Headroom) — local-first context control plane for AI agents
**Version:** v0.30.0 · **HEAD:** `8106b218` · **Last release:** July 4, 2026
**License:** Apache-2.0 (OSS core) + Commercial (EE modules)
**Audience:** Founders, Engineering Lead, Product Lead, GTM
**Methodology:** Codebase audit + competitive intelligence + UX friction analysis across 48 existing audit reports and live CLI/proxy inspection

---

## Executive Summary

**Verdict: STRONG product-market fit on engineering, WEAK product-market fit on commercial readiness. Conditionally ready for design-partner pilot. Not ready for broad OSS or paid enterprise launch.**

Cutctx has built a genuinely differentiated engine — reversible compression (CCR), 5-source savings attribution, 12 specialized compressors, cross-agent memory, proxy-side memory injection, and a Rust core with tree-sitter + stack-graphs. The engineering is ahead of most pre-revenue developer tools.

The three biggest problems are:
1. **The product is invisible.** Three headlines moat features (Feedback Loop, Stack Graphs, Benchmark CLI) have no discoverable CLI surface, no dashboard widgets, and no "How to enable" documentation. Users won't know they exist.
2. **Onboarding is leaky.** The "60-second install" takes 5+ minutes on average, hits SSL friction on corporate networks, leaves 5 of 11 agent wraps requiring manual config paste, and has no welcome state or guided setup.
3. **Commercial infrastructure is absent.** No SOC 2, no SAML SSO, no public pricing page, no TCO calculator, no bug bounty, no security.txt, no GDPR/CCPA DSR cascade complete, and billing has stubs (subscription.updated only recently fixed). Domains (`cutctx.dev`, `cutctx.com`) are NXDOMAIN.

The competitive landscape is bifurcating into "irreversible hosted compression" (Compresr, Token Co., Morph Compact, Condense.chat) vs. "reversible local context runtime" (Cutctx, LeanCTX). Cutctx can own the latter — but must move before LeanCTX (3.1K stars, 1 release/2-3 days) or Condense.chat (launched Jul 3) capture that narrative.

---

## 1. Existing Features — Complete Inventory

### 1.1 Core Compression Engine (🟢 Moat)

| Feature | Details | Defensibility |
|---------|---------|---------------|
| **12 specialized compressors** | SmartCrusher (JSON), CodeCompressor (tree-sitter AST), Kompress-v2 (150M ModernBERT), LogCompressor (Drain3), DiffCompressor, ImageCompressor, AudioCompressor, SearchCompressor, SchemaCompressor, HTMLExtractor, CacheAligner, LLMLingua | HIGH — breadth unmatched |
| **CCR (Reversible Compression)** | Originals cached locally, retrievable via `cutctx_retrieve` tool. Only product doing this. | HIGH — no competitor matches |
| **5-source savings attribution** | Provider prompt cache / Cutctx compression / Semantic cache / Self-hosted prefix cache (vLLM APC) / Model routing | HIGH — no OSS competitor tracks self-hosted prefix cache |
| **Provider-cache-aware compression** | CacheAligner stabilizes KV-cache prefix for provider-side caching | MEDIUM — providers making caching prefix-tolerant |
| **Query-aware compression** | Dynamically adjusts aggressiveness per task type via CompressionHint | MEDIUM |
| **Accuracy guard** | CUTCTX_ACCURACY_GUARD=strict\|balanced\|off | LOW — primitive |
| **Rust core** | PyO3 bindings, tree-sitter + stack-graphs, Ed25519 signing, USearch vector index, SQLite CCR | HIGH — structural, hard to replicate |

### 1.2 Proxy & Routing (🟢 Strong)

| Feature | Details |
|---------|---------|
| **Provider support** | Anthropic (Messages API), OpenAI (Chat + Responses API), Gemini, AWS Bedrock (invoke + streaming + Bedrock Agents), Google Vertex AI (ADC + raw predict), LiteLLM, OpenAI-compatible |
| **Format translation** | Across all providers (streaming + non-streaming) |
| **Batch API** | Proxy-side batch processing |
| **SSE streaming** | Full SSE support across providers |
| **WebSocket** | Real-time session management |
| **Failover routing** | Per-provider failover with EgressEnforcer |
| **Rate limiting** | Per-provider rate limit configuration |
| **Context budget** | Per-session token budget enforcement |
| **Autopilot** | Automated compression strategy selection |
| **~80 admin endpoints** | Health, stats, retention, jobs, secrets, RBAC, SSO via admin router |

### 1.3 CLI (30 Commands) (🟢 Strong)

| Command Category | Commands | Notes |
|-----------------|----------|-------|
| **Setup** | `setup`, `init`, `install` | Unified setup, persistent installs |
| **Runtime** | `proxy`, `mcp`, `wrap`, `intercept` | Start proxy, MCP server, wrap agents, TLS intercept |
| **Memory** | `memory`, `learn`, `policies` | CRUD memories, learn from failures, manage policies |
| **Enterprise** | `audit`, `rbac`, `orgs`, `sso-test`, `license`, `billing` | EE CLI surface |
| **Analytics** | `savings`, `report`, `agent-savings`, `perf` | Savings reporting, scheduled reports, perf analysis |
| **Benchmark** | `bench`, `benchmark`, `evals` | Compression benchmarks, evals |
| **Discover** | `capabilities`, `profile`, `stack-graph`, `integrations` | Capability matrix, compression profile, code nav |
| **Utility** | `config-check`, `tools`, `capture` | Config validation, binary management, traffic capture |

### 1.4 Memory System (🟢 Moat)

| Component | Details |
|-----------|---------|
| **Storage backends** | Local (SQLite), Mem0, USearch, HNSWLib, SQLite-vec |
| **Vector index** | HNSW + USearch via adapters |
| **FTS5 search** | SQLite full-text search for memory |
| **Graph backend** | Knowledge graph with provenance |
| **Cross-agent sync** | Claude Code + Codex sync adapters |
| **Agent writers** | Claude, Codex, Cursor, Generic writers |
| **Memory extraction** | Traffic learner, inline extractor, session-based |
| **Memory injection** | Proxy-side injection (no agent-side tool call needed) |
| **Provenance chains** | Supersession tracking, temporal versioning |
| **Uniqueness** | Only product with proxy-side memory injection + cross-provider cache alignment |

### 1.5 Enterprise Edition (cutctx_ee) (🟡 Building)

| Feature | Status | Notes |
|---------|--------|-------|
| **SSO (OIDC)** | ✅ Working | No SAML (P2 gap) |
| **RBAC** | ✅ Working | Viewer / Memory Curator / Operator / Admin roles; CUTCTX_STRICT_RBAC=1 for fail-closed |
| **SCIM provisioning** | ✅ Implemented | Automatic user provisioning |
| **MFA (TOTP)** | ✅ Implemented | No WebAuthn (P2 gap) |
| **Audit logging** | ✅ HMAC-SHA256 chain | Tamper-evident; DB not append-only (open L-20) |
| **Spend ledger** | ✅ Implemented | Per-org; tenant isolation not complete (M-12) |
| **Billing** | ✅ Invoice.paid, subscription.deleted, subscription.updated fixed. _send_license_email spools only. | No SMTP/SES; no cancellation dunning |
| **Trial management** | ✅ Implemented | License trial start/check |
| **Licensing** | ✅ Ed25519 + ECDSA P-256 | Two formats coexist (H-44) |
| **Watermarking** | ✅ SP-5 per-customer watermarking | V-10 DB query fixed (commit 2da88a43) |
| **Policy enforcement** | ✅ Signed policies with egress enforcer | Air-gap mode |
| **Data residency** | ✅ Ed25519-signed residency proof | No compliance doc |
| **Retention** | ✅ Implemented | Data retention policies |

### 1.6 Dashboard — Web UI (🟡 Basic)

| Page | Purpose | Quality |
|------|---------|---------|
| Overview | High-level metrics | ✅ Functional |
| Capabilities | Runtime capability matrix | ✅ Functional |
| Memory | Memory store viewer | ✅ Functional |
| Firewall | Airgap/policy editor | ✅ Functional |
| Governance | RBAC, SSO, audit | ✅ Functional |
| Orchestrator | Pipeline/compression strategy | ✅ Functional |
| Replay | Session replay | ✅ Functional |
| Playground | Interactive testing | ✅ Functional |
| Docs | In-app documentation | ✅ Functional |

**Dashboard gaps:** No TypeScript, no UI component library (copy-pasted MetricCard/StatusBullet across pages), no i18n, no lazy loading (all pages statically imported), no 404 page, no toast/notification system, no logout button, no onboarding wizard, no dedicated components/hooks/utils directories, form validation is imperative if-checks, dead assets (`hero.png` + `react.svg` + `vite.svg`), SSE streaming not wired (polls every 5s).

### 1.7 IDE Extensions (🟢 Existing but under-documented)

| IDE | Language | Features |
|-----|----------|----------|
| **VS Code** | TypeScript | Start/stop proxy, show stats, configure extension |
| **JetBrains** | Kotlin | Auto-inject HttpConfigurable proxy settings |
| **MCP Server** | Python | MCP tools for Claude Code integration |

### 1.8 Framework Integrations (🟢 Broad)

| Integration | Features |
|-------------|----------|
| **LangChain** | Chat model, agents, LangGraph, LangSmith, memory, retriever, streaming, providers |
| **LlamaIndex** | Response post-processor |
| **Agno** | Hooks, model, providers |
| **Strands (AWS)** | Bundle, hooks, model, providers |
| **LiteLLM** | Callback integration |
| **ASGI** | ASGI middleware |

### 1.9 SDKs (🟢 Unique)

| Language | Maintainer | Status |
|----------|-----------|--------|
| **Python** | First-party | ✅ Full |
| **TypeScript** | First-party | ✅ Full |
| **Go** | First-party | ✅ Full |
| **Go (community)** | Community | ⚠️ |
| **Java (community)** | Community | ⚠️ |

Only product with all 4 first-party SDKs (Python, TypeScript, Go, Java).

### 1.10 Deployment Options (🟢 Broad)

| Method | Status |
|--------|--------|
| **pip install** | ✅ PyPI, trusted publishing |
| **Docker** | ✅ Two-stage build, distroless, healthcheck |
| **docker-compose** | ✅ proxy + qdrant + neo4j |
| **Helm chart** | ✅ v0.30.0, HPA, PDB, ingress, PVC, RBAC |
| **Raw K8s manifests** | ✅ 16 files, Prometheus, FluentBit, backup |
| **Systemd service** | ✅ Via `cutctx install` |
| **LaunchAgent (macOS)** | ✅ Via `cutctx install` |

---

## 2. Missing Features — Capability Gaps

### 2.1 Sell-Blocking Gaps (P0 — fix before first paid customer)

| # | Gap | Impact | Evidence |
|---|-----|--------|----------|
| MF-1 | **SOC 2 Type II certification** | Blocks enterprise procurement. Regulated companies cannot approve without it. | `audit/launch-readiness-report.md` §Enterprise Readiness, launch-readiness-report.md §3 |
| MF-2 | **Verification / Hallucination Guard** | Entroly WITNESS has AUROC 0.844. CISO doing competitive diligence sees the gap. | `audit/production-readiness-2026-07-02.md:292` |
| MF-3 | **Read-side intelligence (10 read modes)** | LeanCTX has full/map/signatures/diff/lines/density/entropy/task/reference/auto. Cutctx only compresses after read. | `audit/production-readiness-2026-07-02.md:293` |
| MF-4 | **SAML SSO** | Enterprise buyers require SAML. OIDC-only blocks deals. | `audit/product-capability-map-2026-06-22.md:359`, `audit/release-audit-verify-2026-07-04.md` |
| MF-5 | **GDPR/CCPA DSR cascade complete** | Spend ledger and audit log delete paths not shipped. GDPR fines for non-compliance. | `audit/product-capability-map-2026-06-22.md:358` |
| MF-6 | **Bug bounty + security.txt + PGP key** | Blocks security-sensitive procurement evaluations. | `audit/launch-readiness-report.md:117-118` |
| MF-7 | **`cutctx.dev` / `cutctx.com` live domains** | 28+ files reference dead NXDOMAIN domains. All security contacts bounce. | `audit/release-audit-verify-2026-07-04.md` |

### 2.2 Competitive Parity Gaps (P1 — fix within 30 days)

| # | Gap | Competitor benchmark | Effort |
|---|-----|---------------------|--------|
| CP-1 | **No hosted SaaS option** | Compresr, Morph Compact, Condense.chat | 2-4 weeks |
| CP-2 | **No public pricing page or TCO calculator** | Portkey, Helicone | 1 week |
| CP-3 | **No security questionnaire packet / SOC 2 report** | Baseten, Portkey | 2 weeks (if SOC 2 audit in progress) |
| CP-4 | **No open quality-at-budget benchmark** | Compresr (CompressBench), LeanCTX (ctx_verify) | 1 week |
| CP-5 | **No CI drift gates for compression quality** | LeanCTX (CI gates via ctx_verify) | 1 week |
| CP-6 | **No virtual key system with per-team budgets** | LiteLLM, Portkey | 2 weeks |
| CP-7 | **No dashboard alerting / notification channels** | Portkey, Helicone | 1 week |
| CP-8 | **No centralized error tracking (Sentry/OTel)** | All competitors | 2 days |
| CP-9 | **No 3rd-party review presence** | Only 3 reviews (neural-nexus.net, miyagadget, andrew.ooo) | Ongoing marketing |
| CP-10 | **No Windows install script** | LeanCTX has PowerShell installer | 3 days |

### 2.3 Product Depth Gaps (P2 — fix this quarter)

| # | Gap | Reason |
|---|-----|--------|
| PD-1 | **Event streaming (SSE) for dashboard** | Dashboard polls every 5s, not EventSource |
| PD-2 | **K8s HA coordination** | Single-writer file; multi-replica needs external coordination |
| PD-3 | **ABAC beyond simple RBAC** | Only role→permission mapping |
| PD-4 | **WebAuthn MFA** | TOTP only |
| PD-5 | **Persistent semantic memory / knowledge graph** | LeanCTX has CCP + property graph; Cutctx's SharedContext is ephemeral |
| PD-6 | **Context verification / tamper-evident savings proof** | LeanCTX has ctx_proof (Ed25519 chain) |
| PD-7 | **Multi-agent coordination / handoff** | LeanCTX has ctx_agent/ctx_handoff |
| PD-8 | **Context Time Machine / snapshots** | LeanCTX has git-anchored signed snapshots |
| PD-9 | **Prompt management / versioning** | Portkey, LangSmith |
| PD-10 | **Deterministic compression mode** | RTK (always deterministic); Cutctx has CodeCompressor (AST) but Kompress is NN-based |

### 2.4 Developer Experience Gaps (P2 — ongoing)

| # | Gap | Impact |
|---|-----|--------|
| DX-1 | **OpenTelemetry / Prometheus metrics for new features** | Feedback Loop, Stack Graphs, Benchmark CLI shipped without instrumentation |
| DX-2 | **Go SDK fully published to Go module registry** | SDK exists but not published |
| DX-3 | **No `cutctx env` command for env var discovery** | 50+ env vars scattered across 5+ modules |
| DX-4 | **No single config file reference** | Mix of TOML, env, and CLI flags |
| DX-5 | **Windows support is degraded** | No prebuilt wheel, no install script, MSVC + Rust required |
| DX-6 | **One-command auto-detection of agent** | RTK has `rtk init -g`; Cutctx requires `cutctx wrap <agent>` |

---

## 3. Competitive Landscape

### 3.1 Competitive Segments

#### Tier 1 — Local-First OSS Analogs (HIGH threat)

| Competitor | Stars | Velocity | Key Differentiator | Cutctx Advantage |
|-----------|-------|----------|-------------------|------------------|
| **LeanCTX** | ~3.1K | 1 release/2-3 days, v3.8.18 | 81 MCP tools, knowledge graph, CCP, ctx_proof, ctx_handoff | CCR reversibility, 5-source attribution, cross-provider cache |
| **Headroom (losi10)** | ~? | Active | Same scope, same name (original), Apache-2.0, no commercial tier | Cutctx has EE features, active development velocity |
| **Clean-CTX / ContextCutter / AgentCTX** | Small | Low | Niche approaches | Breadth of compression algorithms |
| **Edgee** | New | v0.2.10, 23 releases | Edge-deployed, MCP-aware tool-surface reduction | Local-first, reversible, broader enterprise |

#### Tier 2 — Hosted Compression APIs (MEDIUM threat)

| Competitor | Pricing | Differentiator | Cutctx Advantage |
|-----------|---------|---------------|------------------|
| **Compresr** (YC W26) | $0.10/1M tokens | GemFilter, CompressBench leaderboard, LangChain integration | Local-first (data never leaves), reversible, broader algorithm set |
| **Morph Compact** | $0.20/$0.50 per 1M tokens | SOC 2 Type II, GDPR, self-host option, deterministic output, 33K tok/s | Reversibility (CCR), 5-source attribution |
| **Condense.chat** (NEW Jul 3) | Free tier (100M tokens) | Adeline 1 + Helene 1 models, faithfulness leaderboard, 64% reduction | Local-first, reversible, algorithm breadth |
| **Token Company** (YC W26) | $0.30/1M tokens saved | Free 50M tokens/month, simple API | Sub-$1M raised, solo 18yo founder — downgraded threat |

#### Tier 3 — Gateway Feature Absorption (HIGH threat, market vacuum)

| Competitor | Status | Vacuum Opportunity |
|-----------|--------|-------------------|
| **Portkey** | Acquired by Palo Alto Networks for $140M (90 days S2A→exit), repositioned as security product | **VACUUM** — fastest time-to-exit in category. Audience looking for replacement. |
| **Helicone** | Acquired by Mintlify, maintenance mode | **VACUUM** — 0% markup pass-through audience needs a home. |
| **LiteLLM** | BerriAI, 100+ providers, virtual keys, budgets, caching, guardrails | Already has Cutctx as a callback integration — partnership pathway |
| **Cloudflare AI Gateway** | SaaS-only, no local-first | Not a direct threat for local-first buyers |
| **OpenRouter** | Routing-focused | Not a direct threat |

#### Tier 4 — Narrow CLI Wrappers (LOW threat, complementary)

| Competitor | Relationship to Cutctx |
|-----------|----------------------|
| **RTK** (67.5K stars) | **Complementary** — Cutctx SHIPS the RTK binary. RTK handles CLI command output; Cutctx handles agent context. |
| **lean-ctx** (3.1K stars) | Both Tier 1 and Tier 4 — overlapping but more CLI-focused |

### 3.2 Market Trends

1. **Market bifurcating** — "Compression" (irreversible, hosted, API-based) vs. "Curation / context runtime" (reversible, local, policy-based). Cutctx must own the latter.
2. **YC W26 cluster** — 3+ context-compression startups in one batch validates the category but increases competition.
3. **Feature absorption from gateways** — Portkey (PANW), Lakera (Check Point), Helicone (Mintlify) all adding compression. Buyers will increasingly expect it bundled.
4. **MCP is table stakes** — LeanCTX's 81 MCP tools set the bar for integration surface.
5. **Compliance is the enterprise gate** — Morph Compact SOC 2, Portkey HIPAA/ISO, Baseten SOC 2 are table stakes. Cutctx has none.
6. **Portkey/Helicone exits create vacuum** — Audience looking for alternatives, but Condense/Edgee filling fast.

### 3.3 Defensible Moat (What competitors cannot copy)

1. **CCR (reversible compression)** — `cutctx_retrieve` tool. No competitor has this.
2. **5-source savings attribution** — No OSS competitor tracks self-hosted prefix cache as a first-class savings source.
3. **Proxy-side memory injection** — Every other memory tool requires agent to call API/MCP; Cutctx intercepts at proxy layer.
4. **Cross-agent memory + cross-provider cache alignment** — Unique combination.
5. **12-specialist compressor pipeline** — JSON (SmartCrusher), AST code (CodeCompressor), logs (Drain3), diffs, images, audio, HTML, prose (Kompress).
6. **Learn → self-improvement flywheel** — Only capability with a compounding data flywheel.
7. **Complete enterprise surface** — OIDC SSO + RBAC + SCIM + MFA + audit + data residency + air-gap + egress enforcer in one package.
8. **Rust core** (tree-sitter, stack-graphs, Ed25519, USearch) — Hard to replicate architecture.
9. **Local-first + reversible + policy engine** — None of the hosted APIs can offer all three.

---

## 4. User Journey Friction

### 4.1 Installation (Critical friction)

| Step | Experience | Friction |
|------|-----------|----------|
| `pip install "cutctx-ai[all]"` | Prebuilt wheel available (common case) | ✅ Smooth |
| `pip install "cutctx-ai[all]"` on Windows/Intel Mac | Falls back to sdist → requires Rust toolchain | 🔴 15+ min detour |
| Corporate network with SSL inspection | `CERTIFICATE_VERIFY_FAILED` → manual Rust install | 🔴 Blocks install |
| Choosing extras | 21+ optional extras; `[all]` omits many popular ones | 🟡 Confusing |
| Wiki docs | Use stale `pip install cutctx` (wrong package name) | 🟡 Broken links |
| CLI help first-run | 5+ commands show "Unavailable in this installation" | 🟡 Noise |

### 4.2 First-Use Experience (Critical friction)

| Step | What happens | Friction |
|------|-------------|----------|
| `cutctx setup` | 5-step sequential flow, no welcome screen | 🟡 Anemic |
| `cutctx wrap claude` | Works beautifully — one command, proxy starts | ✅ Magic |
| `cutctx wrap cursor` | Prints manual config instructions — must paste into Cursor settings | 🟡 Broken promise |
| `cutctx wrap windsurf` | Prints instructions, doesn't write them | 🟡 Broken promise |
| `cutctx wrap zed` | Prints `settings.json` snippet | 🟡 Broken promise |
| `cutctx memory` | "Unavailable in this installation (missing optional...)" | 🟡 Bad UX |
| Dashboard first load | No welcome state, $0.00 with no guidance | 🔴 Cold start |
| `cutctx capabilities` | 3 moat features not listed | 🔴 Invisible |
| `cutctx profile show` | Exists but not in quickstart or README | 🟡 Hidden |

### 4.3 Agent Wrap UX (The "one-command" promise vs. reality)

| Agent | Wrap command | Config method | Friction |
|-------|-------------|---------------|----------|
| Claude Code | `cutctx wrap claude` | Auto-writes `~/.claude/settings.json` + MCP registration | ✅ Zero |
| Codex | `cutctx wrap codex` | Auto-writes `~/.codex/config.toml` with marker blocks | ✅ Zero |
| Cursor | `cutctx wrap cursor` | **Prints instructions** — user must paste into Cursor settings | 🟡 Manual |
| Windsurf | `cutctx wrap windsurf` | **Prints instructions** | 🟡 Manual |
| Zed | `cutctx wrap zed` | **Prints settings.json snippet** | 🟡 Manual |
| Cline | `cutctx wrap cline` | **Prints VS Code config** | 🟡 Manual |
| Continue | `cutctx wrap continue` | **Prints VS Code/JetBrains config** | 🟡 Manual |
| Aider | `cutctx wrap aider` | Auto-writes `.aider.conf.yml` | ✅ Zero |
| Copilot | `cutctx wrap copilot` | CLI wrap via `cutctx wrap copilot-cli` | 🟡 OS keychain issues |
| OpenCode | `cutctx wrap opencode` | Sets ANTHROPIC_BASE_URL | ✅ Zero |

**5 of 11 wraps (45%) require manual config paste.** This is the single biggest UX gap for the "one command" narrative.

### 4.4 Configuration Complexity

| Dimension | Count | Assessment |
|-----------|-------|------------|
| Optional extras in pyproject.toml | 21+ | 🟡 Fragmented |
| Environment variables | 50+ read across 5+ modules | 🔴 Proliferation |
| Config file formats | TOML (CLI), env vars (proxy), JSON (agent configs) | 🟡 Fragmented |
| Feature flags (env-var-only) | 12+ (`CUTCTX_*_ENABLED=1`) | 🟡 No central registry |
| Memory backends | 4 (AUTO, sqlite-vec, usearch, hnswlib) | 🟡 Confusing selection |

---

## 5. Onboarding Issues

### 5.1 No Welcome State

The dashboard has no first-run detection, no welcome screen, no guided setup, no "what now" prompt after install. A user who runs `cutctx setup` and opens the dashboard sees `$0.00` with zero guidance. This has been flagged in 4 separate audits.

### 5.2 Three Moat Features Are Invisible

| Feature | CLI Discovery | Dashboard | "How to enable" doc |
|---------|--------------|-----------|---------------------|
| **Feedback Loop** | `cutctx profile show` exists but not surfaced | No widget (never added) | None |
| **Stack Graphs** | `cutctx stack-graph explain` exists | `FeatureAvailabilityPanel` exists | Minimal |
| **Benchmark CLI** | Hidden under `cutctx evals benchmark` | No integration | README references old suite |

All three were flagged as **Critical** in the audit friction table (`final-verdict.md`).

### 5.3 Documentation Gap

| Issue | Location | Severity |
|-------|----------|----------|
| Stale `pip install cutctx` (should be `cutctx-ai`) | `wiki/getting-started.md:11`, `wiki/quickstart.md:13` | 🟡 High |
| Product Guide says v0.26.x→v0.27.0 (actual is 0.30.0) | `PRODUCT_GUIDE.md:42` | 🟡 Medium |
| Two competing Quick Start stories | `__init__.py` docstring vs `wiki/index.md` | 🟡 Medium |
| No "How to enable" doc for Feedback Loop | Missing entirely | 🔴 Critical |
| `[all]` extra docs don't mention what it omits | `README.md`, `installation.mdx` | 🟡 Medium |
| No per-compression-ratio accuracy curves | Docs publish aggregate accuracy only | 🟡 Low |
| compress SKILL.md had 5 incorrect claims | Fixed via adversarial testing | 🟡 Medium (historical) |

### 5.4 Known Setup Failures

| Failure Mode | Frequency | Resolution |
|-------------|-----------|------------|
| SSL `CERTIFICATE_VERIFY_FAILED` | Common (corporate) | Manual Rust install |
| `pip install` fails on Windows | Frequent (no wheel) | MSVC + Rust toolchain |
| Air-gap: HF model download | Every air-gap install | Pre-download + env vars |
| `cutctx memory` unavailable | Every non-memory install | Add `[memory]` extra |
| Issue #746: Claude context expansion | Every Claude wrap | Workaround in wrap.py (ENABLE_TOOL_SEARCH) |

---

## 6. Retention Issues

### 6.1 Agent-Update Brittleness

Agent wrappers edit external config files (`~/.claude/settings.json`, `~/.codex/config.toml`, etc.) via marker-based block injection. If any of these agents change their:
- Internal configuration paths
- CLI arguments
- Settings JSON schema
- MCP protocol version

...`cutctx wrap` commands break silently. The user sees an error or, worse, a silently non-functional proxy.

| Agent | Config file edited | Breakage risk |
|-------|-------------------|---------------|
| Claude Code | `~/.claude/settings.json` | **HIGH** — Anthropic iterates fast |
| Codex | `~/.codex/config.toml` | **HIGH** — OpenAI iterates fast |
| Cursor | Manual paste only | **LOW** — no auto-config to break |
| Windsurf | Manual paste only | **LOW** — no auto-config to break |
| Aider | `.aider.conf.yml` | **MEDIUM** — stable but versioned |

### 6.2 Trust in Reversibility

CCR is Cutctx's strongest moat, but it depends on the LLM calling `cutctx_retrieve`:
- Weaker models may not realize they should use the retrieval tool
- Improper prompting leads to the user perceiving compression as lossy
- Once perceived as lossy, the user uninstalls

**Current mitigations:** Proactive expansion logic (`CUTCTX_NO_CCR_PROACTIVE_EXPANSION`), tool injection at proxy layer, accuracy guard. **No user-facing metrics show retrieval rates.**

### 6.3 Memory Bloat

Despite semantic deduplication:
- Long-lived projects accumulate large memory databases
- Vector search relevance degrades as the index gets noisy
- `processed_events` dedup table has no TTL cleanup
- No memory compaction or archival workflow
- No user-facing "memory health" indicator

### 6.4 Silent Failures

| Failure | Detection | Impact on retention |
|---------|-----------|-------------------|
| Proxy stops, agent falls back to direct API | User eventually notices savings stopped | **👋 Churn** |
| Issue #746: Claude context inflates silently | Only visible via `/context all` | **👋 Churn** |
| EE stub routes silently 404 | User gets no error, just no feature | **😐 Friction** |
| Dashboard asset serving 404 (pre-fix) | Dashboard rendered empty | **👋 Churn** |
| `CUTCTX_ACCURACY_GUARD` misconfiguration | No feedback about impact of each setting | **😐 Friction** |

### 6.5 Pricing → Retention Pathway

| Tier | Price | Retention mechanism | Risk |
|------|-------|-------------------|------|
| **Builder** (OSS) | $0 | No lock-in; user stays if it works | **HIGH** — easy to leave |
| **Team** | $18K/yr | Configuration + memory + policy investment | **MEDIUM** |
| **Business** | $42K/yr | Multi-project, team RBAC, audit | **LOW** — switching cost high |
| **Enterprise** | $60-150K+/yr | Compliance, air-gap, SLA | **VERY LOW** — high switching cost |

The free tier has no retention mechanism beyond "it works." There is no:
- Free memory sync across sessions (without paid tier)
- Free community/team features that create lock-in
- Free usage tier with limits that encourage upgrade

---

## 7. Competitive Positioning & Go-To-Market

### 7.1 Category Position

Cutctx should own **"reversible local context runtime for AI agents"** — not "compression."

| Claim | Messaging | Evidence |
|-------|-----------|----------|
| **Govern** | "Prove what was sent, retrieved, and saved. Audit trail, RBAC, data residency, air-gap." | CCR, audit chain, air-gap, egress enforcer |
| **Attribute** | "Know exactly where every dollar went: provider caching, compression, semantic cache, self-hosted prefix, model routing." | 5-source savings attribution |
| **Compound** | "Context compounds across agents and sessions. Memory, Learn, and Feedback Loop create a growing org context store." | Cross-agent memory, cutctx learn, Feedback Loop |

### 7.2 Buyer Personas

| Persona | Title | Trigger | Buying Criteria |
|---------|-------|---------|-----------------|
| **Champion** | Staff AI Engineer | Token bills too high, agent context loss | "Works with our stack, reversible, measurable savings" |
| **Economic buyer** | VP Engineering | 50%+ cloud AI cost growth month-over-month | ROI in dollars, not compression ratios |
| **Technical evaluator** | SecOps / InfoSec | Data sent to third-party API for compression | "Data never leaves, audit trail, air-gap mode" |

### 7.3 Pricing

| Tier | Price | Target | What's included |
|------|-------|--------|-----------------|
| **Builder** | $0 | Individual OSS users | Core compression, CLI, proxy |
| **Team** | $1,500/mo ($18K/yr) | Single engineering team | Everything + EE features + dashboard |
| **Business** | $3,500/mo ($42K/yr) | Platform teams, multi-project | Team + multi-project + audit + RBAC |
| **Enterprise** | $60-150K+/yr | Security-sensitive, procurement | Business + on-prem + SLA + compliance |

### 7.4 Competitive Positioning Statements

**vs. Hosted compression APIs (Compresr, Token Co., Morph Compact):**
> "They compress in the cloud and send it back. Cutctx never lets the data leave — compression happens locally against your own proxy. And if the LLM needs the original, CCR retrieves it. That's not what hosted APIs offer."

**vs. Gateway platforms (Portkey, Helicone, LiteLLM):**
> "They route traffic. Cutctx transforms it — compression, policy, memory, savings attribution — all before it reaches the model. Gateways add latency; Cutctx reduces token count and caches intelligently."

**vs. Provider-native features (OpenAI Compaction, Anthropic cache_control):**
> "Provider caching works on prefixes within one provider. Cutctx compresses tool outputs, logs, diffs, and code search — payloads native caching doesn't touch. And we work across providers."

**vs. LeanCTX (most direct OSS competitor):**
> "LeanCTX compresses CLI commands. Cutctx compresses everything an AI agent touches — and keeps the original retrievable. Reversibility is the difference between 'lost context' and 'compound context.'"

---

## 8. Prioritized Recommendations

### P0 — Fix Immediately (Before Any Paid Deal)

| # | Action | Effort | Impact |
|---|--------|--------|--------|
| 1 | **Register cutctx.dev website** — fix 28+ broken docs links, enable security contacts | 1 day | Unblocks security evaluation |
| 2 | **Make 3 moat features discoverable** — add Feedback Loop, Stack Graphs, Benchmark CLI to `cutctx capabilities` table; add CLI docstrings showing entry points | 1 day | Resolves 3 Critical friction items |
| 3 | **Start SOC 2 Type II audit process** — 6+ month lead time, start now or lose Q1 2027 deals | $50-100K | Blocks enterprise procurement |
| 4 | **Implement verification/hallucination guard** — competitive disadvantage vs. Entroly WITNESS | 2-3 weeks | CISO diligence gap |
| 5 | **Implement read-side intelligence** — 10 read modes parity with LeanCTX | 1 week | Feature parity gap |

### P1 — Fix This Month (Before Broad OSS Release)

| # | Action | Effort |
|---|--------|--------|
| 6 | Add onboarding wizard to dashboard (welcome state for zero-traffic users) | 3 days |
| 7 | Complete auto-write for Cursor, Windsurf, Zed, Cline, Continue wraps | 2-3 days |
| 8 | Publish public pricing page + TCO calculator | 1 week |
| 9 | Add SSE streaming to dashboard (replace polling) | 2-3 days |
| 10 | Publish open quality-at-budget benchmark (CompressBench or similar) | 1 week |
| 11 | Add centralized error tracking (Sentry/OTel exporter) | 2 days |
| 12 | Add dashboard alerting for error rate, backup failure, license expiry | 3 days |
| 13 | Set up dependency vulnerability scanning (Dependabot cargo + SAST in CI) | 1 day |
| 14 | Fix stale wiki docs (package name, version, install instructions) | 1 day |

### P2 — Fix This Quarter (Before v1.0)

| # | Action | Effort |
|---|--------|--------|
| 15 | SAML SSO | 1 week |
| 16 | WebAuthn MFA | 1 week |
| 17 | Expand backup coverage beyond 3 stores (RBAC, billing, webhook DLQ, graph) | 2 days |
| 18 | Enable `CUTCTX_STRICT_RBAC=1` by default for new installs | 1 day |
| 19 | Add TTL cleanup for `processed_events` dedup table | 0.5 day |
| 20 | Add virtual key system with per-team budgets | 2 weeks |
| 21 | Windows install script + prebuilt wheels for all platforms | 1 week |
| 22 | Public security.txt + bug bounty program launch | 1 week |
| 23 | Add per-compression-ratio accuracy curves to docs | 2 days |
| 24 | Add "memory health" indicator to dashboard | 2 days |

### P3 — Track for Next Milestone

| # | Action |
|---|--------|
| 25 | Persistent semantic memory / knowledge graph |
| 26 | Multi-agent coordination / handoff |
| 27 | Context Time Machine / snapshots |
| 28 | Prompt management / versioning |
| 29 | Deterministic compression mode |
| 30 | Go SDK published to Go module registry |
| 31 | Single config file (`cutctx.env` or `cutctx.toml`) |
| 32 | API versioning on admin endpoints |
| 33 | ABAC beyond simple RBAC |
| 34 | Add 3rd-party review program + case studies |

---

## 9. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **LeanCTX captures "local context runtime" narrative** | HIGH | Critical | Ship Feedback Loop discoverability + benchmark within 2 weeks |
| **Condense.chat absorbs Portkey/Helicone vacuum** | HIGH | High | Target Portkey/Helicone audience in outreach; position as "local-first control plane" |
| **SOC 2 audit blocks Q1 2027 deals** | MEDIUM | Critical | Start audit process now (6+ month lead time) |
| **Agent wrapper brittleness causes churn** | MEDIUM | High | Add integration tests + fallback detection for agent config format changes |
| **CCR trust failure (LLM doesn't retrieve)** | MEDIUM | High | Add retrieval rate metrics to dashboard; improve tool injection reliability |
| **Memory bloat degrades performance on long-lived projects** | MEDIUM | Medium | Add TTL, compaction, health indicator |
| **Provider-native features absorb compression value** | HIGH | Medium | Continue positioning Cutctx as cross-provider policy + attribution layer |
| **20+ feature flags default-off means proxy starts in near-pass-through state** | MEDIUM | Medium | Add "recommended settings" preset that enables the most impactful ones |

---

## 10. Key Metrics to Track

| Metric | Current Baseline | Target |
|--------|-----------------|--------|
| Test suite health | 7,763 passed / 0 failed | Maintain |
| Dashboard UX rating | Not measured | >80/100 (user survey) |
| Install-to-first-wrap conversion | Not measured | >70% |
| Agent wrap success rate | ~55% (6/11 one-command) | >90% |
| CCR retrieval rate | Not measured in dashboard | >30% |
| 30-day retention (OSS) | Not measured | >60% |
| Paid pilot → paid conversion | N/A (no pilots yet) | >50% |
| Features discoverable on first run | 0 (no welcome state) | All headline features |
| Documentation freshness (stale link %) | ~10-15% | <2% |

---

## Appendix: Key Sources

- `audit/release-audit-verify-2026-07-04.md` — Verification audit (83/100)
- `audit/release-audit-2026-07-04.md` — Release audit (86/100)
- `audit/code-review-report.md` — Code quality + security review (402 lines)
- `audit/launch-readiness-report.md` — Launch readiness (501 lines, 5.5/10)
- `audit/production-readiness-2026-07-04.md` — Production readiness (63/100)
- `audit/production-readiness-assessment.md` — Production assessment (55/100)
- `audit/competitor-report.md` — Competitive analysis (203 lines)
- `audit/product-manager-report.md` — Prior PM report (35 lines, superseded)
- `audit/product-capability-map-2026-06-22.md` — Capability map vs OSS LLM proxies
- `audit/comprehensive-capability-report.md` — Comprehensive capability report
- `audit/paas-readiness-assessment.md` — PaaS readiness assessment
- `audit/final-verdict.md` — Final verdict with friction table
- `artifacts/product-strategy-moat-analysis.md` — Strategic moat analysis (91 lines)
- `artifacts/value-proposition.md` — Value proposition (159 lines)
- `artifacts/pricing-sheet.md` — Pricing (212 lines)
- `artifacts/outreach-current-positioning.md` — Current positioning (97 lines)
- `gtm/cutctx-comprehensive-acquisition-plan.md` — GTM acquisition plan (143 lines)
- `wiki/LIMITATIONS.md` — Honest limitation doc
- `PRODUCT_GUIDE.md` — Product guide (913 lines)
- `README.md` — README (25KB)

---

*Report generated July 4, 2026. Based on codebase audit at `/Users/aryansingh/Documents/Claude/Projects/headroom` (v0.30.0, HEAD 8106b218), competitive intelligence from 48+ audit reports, and live CLI/proxy inspection.*
