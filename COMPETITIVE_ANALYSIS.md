# Headroom — Competitive Analysis

**Date:** 2026-06-15
**Version:** 1.0
**Scope:** Top 10 context compression / token optimization tools for AI agents

---

## Executive Summary

Headroom is a context compression layer for AI agents with: library (Python/TypeScript), proxy mode, agent wrapping, MCP server, 6 compression algorithms, cross-agent memory, reversible compression (CCR), Kompress-v2-base model on HuggingFace, and `headroom learn` for learning from failed sessions. It achieves 60-95% token reduction. Apache 2.0 licensed, published on PyPI and npm.

**Market Position:** Headroom occupies a unique and strong position as the most comprehensive, agent-specific compression solution with reversible compression and cross-agent memory. Primary gaps are provider-specific optimizations, KV cache integration, and real-time compaction speed.

---

## Competitive Matrix

| Tool | Compression | Reversible | Cross-Agent Memory | Agent Integration | Pricing |
|------|-------------|------------|-------------------|-------------------|---------|
| **Headroom** | 60-95% | ✅ CCR | ✅ | ✅ Wrap/Proxy/MCP | Open Source |
| LLMLingua-2 | 10-20x | ❌ | ❌ | ❌ | Open Source |
| AutoCompressor | Variable | ❌ | ❌ | ❌ | Open Source |
| Gisting | Up to 26x | ❌ | ❌ | ❌ | Research |
| CacheBlend | N/A (caching) | N/A | ❌ | vLLM only | Open Source |
| LangChain | Variable | ❌ | ❌ | LangChain only | Open Source |
| Anthropic Caching | N/A (caching) | ❌ | ❌ | Claude only | Included |
| OpenAI Caching | N/A (caching) | ❌ | ❌ | OpenAI only | Included |
| Morph Compact | 50-70% | ❌ (verbatim) | ❌ | API only | Commercial |
| lean-ctx | 89-99% | ❌ | ✅ CCP | 22+ agents | Open Source |
| RTK | 60-90% | ❌ | ❌ | Shell hook | Open Source |

---

## Competitor Deep-Dives

### 1. LLMLingua / LLMLingua-2 (Microsoft Research)
- **Approach:** Token-level classification with GPT-4 distillation
- **Compression:** Up to 20x (1.5% accuracy drop)
- **Strengths:** Strong academic validation, highest compression ratios in benchmarks
- **Weaknesses:** Lossy, no agent features, no reversible compression, no memory
- **Headroom advantage:** Reversible (CCR), multi-algorithm, cross-agent memory, agent wrapping

### 2. CacheBlend (ACM EuroSys'25 Best Paper)
- **Approach:** KV cache fusion for RAG applications
- **Compression:** Near-100% KV cache hit rate, 3x TTFT reduction
- **Strengths:** Dramatic RAG speedup, production-ready via LMCache
- **Weaknesses:** RAG-specific, requires vLLM, not standalone compression
- **Headroom advantage:** General-purpose, works with any provider, reversible

### 3. Morph Compact
- **Approach:** Byte-identical verbatim deletion at 33,000 tok/s
- **Compression:** 50-70% via query-aware deletion
- **Strengths:** Extremely fast, byte-identical output, no hallucination risk
- **Weaknesses:** Commercial, deletion-only, no reversible, no memory
- **Headroom advantage:** Multi-algorithm, reversible, cross-agent memory, open source

### 4. lean-ctx (Lean Cortex)
- **Approach:** Hybrid Rust binary with 62 MCP tools, 95+ shell patterns
- **Compression:** 89-99% token reduction
- **Strengths:** Extreme reduction, works with 22+ agents, session caching
- **Weaknesses:** Primarily shell/file focused, no reversible compression
- **Headroom advantage:** Reversible (CCR), ContentRouter for all content types, HuggingFace model

### 5. RTK (Rust Token Kit)
- **Approach:** CLI proxy with 4 compression strategies for 50+ commands
- **Compression:** 60-90% on CLI output
- **Strengths:** Simple shell hook integration, command-specific patterns
- **Weaknesses:** CLI-only, no memory, no multi-algorithm
- **Headroom advantage:** Full-stack compression (not just CLI), MCP server, reversible

### 6-10: Provider-Native Caching (Anthropic/OpenAI), LangChain, AutoCompressor, Gisting
- Detailed in research — mostly lossy or provider-locked, no agent-specific features

---

## Headroom's Unique Advantages

1. **Reversible Compression (CCR)** — Only tool that stores originals and provides retrieval tools
2. **6 Specialized Algorithms** — SmartCrusher (JSON), CodeCompressor (AST), Kompress-base (text), CacheAligner, Image, IntelligentContext
3. **Cross-Agent Memory** — Shared store across Claude Code, Codex, Gemini
4. **Agent Wrapping** — One-command: `headroom wrap claude|codex|cursor|aider`
5. **MCP Server** — `headroom_compress`, `headroom_retrieve`, `headroom_stats`
6. **Headroom Learn** — Mines failed sessions, writes corrections to CLAUDE.md/AGENTS.md
7. **CacheAligner** — Optimizes system prompts for KV cache hit rates

---

## Performance Benchmarks

| Workload | Before | After | Savings |
|----------|--------|-------|---------|
| Code search (100 results) | 17,765 tokens | 1,408 tokens | 92% |
| SRE incident debugging | 65,694 tokens | 5,118 tokens | 92% |
| GitHub issue triage | 54,174 tokens | 14,761 tokens | 73% |
| Codebase exploration | 78,502 tokens | 41,254 tokens | 47% |

---

## Top 5 Critical Gaps

### Gap 1: Provider-Specific Optimizations (MEDIUM)
**Competitors:** Anthropic Compaction API, OpenAI Prompt Caching
**Issue:** Provider-native solutions offer zero-config optimization. Headroom is agnostic but could benefit from tighter integration.
**Recommendation:** Add provider-specific modules that leverage Anthropic/OpenAI caching when available.

### Gap 2: KV Cache Optimization (MEDIUM)
**Competitors:** CacheBlend (100% hit rate)
**Issue:** CacheAligner optimizes prompt ordering but doesn't address KV cache reuse at inference level.
**Recommendation:** Integrate CacheBlend-style KV cache optimization for RAG workloads.

### Gap 3: Real-Time Compaction Speed (LOW-MEDIUM)
**Competitors:** Morph Compact (33,000 tok/s)
**Issue:** For large-scale production deployments with strict latency, speed matters.
**Recommendation:** Publish detailed latency benchmarks. Consider speed-optimized compression tier.

### Gap 4: Verbatim Fidelity Guarantee (LOW)
**Competitors:** Morph Compact (byte-identical output)
**Issue:** Coding agents need exact file paths and line numbers preserved.
**Recommendation:** Headroom's CCR provides this via retrieval, but document the guarantee explicitly.

### Gap 5: Ecosystem Integration Depth (MEDIUM)
**Competitors:** lean-ctx (22+ agents)
**Issue:** Emerging agent frameworks need broader coverage.
**Recommendation:** Target 25+ supported agents. Add integration guides for newer tools.

---

## Market Positioning

Headroom sits at the intersection of three markets:
1. **Context compression** (vs. LLMLingua, Morph Compact)
2. **Agent infrastructure** (vs. lean-ctx, RTK)
3. **Token optimization** (vs. provider-native caching)

**Unique moat:** Reversible compression + cross-agent memory + headroom learn. No competitor offers all three.

---

## Strategic Recommendations

1. **Enhance KV Cache integration** — CacheBlend-style optimization for RAG
2. **Benchmark against Morph Compact** — Direct speed + fidelity comparison
3. **Expand agent coverage** — Target 25+ supported agents
4. **Add provider-specific optimizers** — Leverage Anthropic/OpenAI caching
5. **Publish latency benchmarks** — Prove production readiness

---

*Analysis compiled June 2026 from official docs, GitHub repos, research papers, and industry benchmarks.*
