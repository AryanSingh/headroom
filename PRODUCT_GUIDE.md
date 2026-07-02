# Cutctx — Complete Product Guide
*For sales conversations, technical evaluations, and deep understanding*

---

## Table of Contents

1. [What is Cutctx?](#1-what-is-cutctx)
2. [The Core Problem It Solves](#2-the-core-problem-it-solves)
3. [How It Works — Architecture](#3-how-it-works--architecture)
4. [The Compression Pipeline](#4-the-compression-pipeline)
5. [CCR — Reversible Compression](#5-ccr--reversible-compression)
6. [Deployment Modes](#6-deployment-modes)
7. [Agent Compatibility](#7-agent-compatibility)
8. [Memory System](#8-memory-system)
9. [Cutctx Learn — Agent Self-Improvement](#9-cutctx-learn--agent-self-improvement)
10. [Enterprise Features](#10-enterprise-features)
11. [Security & Privacy](#11-security--privacy)
12. [Integrations](#12-integrations)
13. [Pricing & Tiers](#13-pricing--tiers)
14. [ROI & Business Case](#14-roi--business-case)
15. [Competitive Landscape](#15-competitive-landscape)
16. [Benchmarks & Proof Points](#16-benchmarks--proof-points)
17. [Installation & Setup](#17-installation--setup)
18. [Sales Objection Handling](#18-sales-objection-handling)
19. [Pitch by Audience](#19-pitch-by-audience)
20. [Quick-Reference FAQ](#20-quick-reference-faq)

---

## 1. What is Cutctx?

**Cutctx is the local-first context control plane for AI agents.** It sits between your AI agents (Claude Code, Cursor, Codex, etc.) and LLM providers (Anthropic, OpenAI, Google, Bedrock), governs what reaches the model, attributes spend and savings, preserves reversible access to originals, and helps teams reuse memory across sessions and tools.

**One-liner:** Govern what enters context. Attribute where tokens go. Compound what your agents learn.

**Product brand:** Cutctx  
**PyPI package:** `cutctx-ai`  
**npm package:** `cutctx-ai`  
**Python module:** `cutctx` (historical; `cutctx` alias works)  
**License:** Open-core — Apache 2.0 for the engine; proprietary for EE/commercial modules  
**Current version:** v0.26.x → v0.27.0  

---

## 2. The Core Problem It Solves

Every AI agent reads enormous amounts of data during its work:

- A code search returns 100 files — 17,000+ tokens
- An SRE agent reads incident logs — 65,000+ tokens
- A GitHub issue triage reads comments and diffs — 54,000+ tokens
- A codebase exploration reads file trees and contents — 78,000+ tokens

**70–95% of this is boilerplate.** Repetitive log lines, identical JSON fields, code comments, passing test output, HTML markup — none of it helps the LLM answer the question. But it all burns tokens, pushes up cost, and fills the context window.

The result: agents hit context limits and fail, bills grow with every API call, and engineers waste time working around token limits instead of building.

**Cutctx compresses all of it away before it hits the model.** The LLM sees the signal, not the noise.

---

## 3. How It Works — Architecture

```
 Your agent / app
 (Claude Code, Cursor, Codex, LangChain, Agno, Strands, your own code…)
      │   prompts · tool outputs · logs · RAG results · files
      ▼
 ┌────────────────────────────────────────────────────┐
 │  Cutctx    (runs locally — your data stays here)  │
 │  ────────────────────────────────────────────────  │
 │  CacheAligner  →  ContentRouter  →  CCR            │
 │                    ├─ SmartCrusher   (JSON)        │
 │                    ├─ CodeCompressor (AST)         │
 │                    ├─ Kompress-base  (text/prose)  │
 │                    ├─ LogCompressor  (logs)        │
 │                    ├─ DiffCompressor (git diffs)   │
 │                    ├─ Drain3         (ML logs)     │
 │                    └─ Graphify       (code graph)  │
 │                                                    │
 │  Cross-agent memory  ·  Cutctx Learn  ·  MCP      │
 └────────────────────────────────────────────────────┘
      │   compressed prompt  +  retrieval tool
      ▼
 LLM provider  (Anthropic · OpenAI · Bedrock · Vertex · Azure · 100+ via LiteLLM)
```

Three stages happen on every request:

**Stage 1 — CacheAligner:** Stabilizes message prefixes so the provider's KV cache hits. Anthropic gives a 90% read discount on cached prefixes. CacheAligner makes that discount actually work by ensuring prefixes don't shift between requests.

**Stage 2 — ContentRouter:** Auto-detects content type (JSON, code, logs, diffs, HTML, plain text) and routes each piece to the optimal compression algorithm. No configuration needed — it figures it out automatically.

**Stage 3 — IntelligentContext:** If the conversation still exceeds the context limit after compression, it scores each message by importance (recency, references, information density) and drops the lowest-value ones. Dropped content goes into CCR so it can be retrieved if needed.

---

## 4. The Compression Pipeline

Cutctx has 12 compression algorithms, each specialized for a content type:

| Content Type | Algorithm | How It Works | Typical Savings |
|---|---|---|---|
| JSON arrays / tool outputs | **SmartCrusher** | Statistical analysis — keeps outliers, errors, boundaries; collapses repetition. No hardcoded rules. | 80–95% |
| Source code | **CodeCompressor** | AST-aware via tree-sitter. Preserves function signatures, collapses bodies. Works for Python, JS, Go, Rust, Java, C++. | 60–80% |
| Plain text / prose | **Kompress-base** | HuggingFace model (`kompress-v2-base`) trained on agentic traces. ModernBERT token classification removes redundant tokens while preserving meaning. | 30–60% |
| Build / test logs | **LogCompressor** | Keeps failures, errors, warnings. Drops passing test noise. Uses aho-corasick pattern detection. | 85–95% |
| Git diffs | **DiffCompressor** | Preserves change hunks, strips metadata and unchanged context. | 50–70% |
| Git diffs (structural) | **Difftastic** (`--difftastic`) | AST-aware structural diffs. Moved code = 0 lines, whitespace ignored. 30+ languages. | 60–95% |
| Repetitive log lines | **Drain3** (`--drain3`) | ML template mining — groups repetitive log lines by structural template, emits one representative + count. 10–50× better than statistical sampler. | 90–98% |
| File reads / code queries | **Graphify** (`--knowledge-graph`) | Builds a codebase-wide semantic graph. BFS subgraphs replace full file reads with ~15 tokens/node vs ~800 tokens/file. | 95%+ |
| HTML | **HTMLExtractor** | Strips markup, extracts readable content. | 70–90% |
| Search results | **SearchCompressor** | Ranks by relevance to user query, keeps top matches. | 70–90% |
| Images | **Image Compressor** | JPEG quality routing + format conversion. ML router selects optimal resize/quality tradeoff per image. | 40–90% |
| JSON tool schemas | **Schema Compressor** | Strips 32 redundant metadata keys from tool definitions. | ~40% |

### Accuracy Guard

Before forwarding any compressed output, Cutctx runs safety checks to verify critical identifiers, function names, and references are preserved. Configurable via `CUTCTX_ACCURACY_GUARD=strict|balanced|off`.

### CompactTable

For JSON arrays of homogeneous objects (file listings, DB rows, search results), Cutctx serializes them into a compact pipe-delimited table format — 30–60% smaller than JSON. Auto-activates for arrays of 5+ dicts.

### Query-Aware Compression

Cutctx detects the task type from the last user message (CODE, DEBUG, SEARCH, LIST, SUMMARIZE, etc.) and automatically tunes compression aggressiveness:
- CODE/DEBUG: conservative — protects the last 6 conversation turns
- SEARCH/LIST/SUMMARIZE: aggressive — protects only the last 2 turns

---

## 5. CCR — Reversible Compression

**This is Cutctx's key differentiator.** Traditional compression is lossy — if you throw away the wrong thing, it's gone. CCR (Compress-Cache-Retrieve) eliminates this risk entirely.

### How CCR Works

1. **Compress:** Content is compressed (e.g., 1,000 JSON items → 20 representative items)
2. **Cache:** The original is stored locally with a hash key
3. **Mark:** A retrieval marker is injected: `[1000 items compressed to 20. Retrieve more: hash=abc123]`
4. **Retrieve:** A `cutctx_retrieve` tool is available to the LLM. If it needs the full data, it calls this tool.
5. **Transparent:** The proxy intercepts the tool call, returns the cached original, and continues the API call — **the client app never sees any of this.**

```
Turn 1: 1,000 items → 20 shown, 1,000 cached
  Option A: LLM solves with 20 items → Done (95% savings)
  Option B: LLM calls cutctx_retrieve(hash=abc123)
            → Proxy returns full 1,000 items automatically
            → LLM answers accurately
```

### Multi-Turn Context Tracking

The Context Tracker watches what was compressed in earlier turns. If a later query looks relevant to compressed content, it proactively expands it:

```
Turn 1: 500 files compressed to 15, cached
Turn 5: User asks "What about the auth middleware?"
       → Context Tracker: "auth" probably in the cached file list
       → Automatically expands before the LLM asks
       → LLM finds auth_middleware.py
```

### Why It Matters for Sales

The #1 fear buyers have about compression is "what if it throws away something important?" CCR completely neutralizes that fear. You can compress as aggressively as you want — the original is always available on demand. **Best of both worlds: cheap context on the wire, full fidelity on demand.**

---

## 6. Deployment Modes

Cutctx offers four ways to integrate — pick whichever fits your stack:

### Mode 1: Proxy (Zero Code Changes)

```bash
pip install "cutctx-ai[all]"
cutctx proxy --port 8787
# Then point any tool at the proxy:
ANTHROPIC_BASE_URL=http://localhost:8787 claude
OPENAI_BASE_URL=http://localhost:8787/v1 your-app
```

Any OpenAI-compatible or Anthropic-compatible client works. No code changes. Every request goes through Cutctx automatically.

### Mode 2: Agent Wrap (One Command)

```bash
cutctx wrap claude       # Claude Code
cutctx wrap codex        # OpenAI Codex CLI
cutctx wrap cursor       # Cursor
cutctx wrap aider        # Aider
cutctx wrap copilot      # GitHub Copilot CLI
cutctx wrap windsurf     # Windsurf
cutctx wrap zed          # Zed
cutctx wrap opencode     # OpenCode
```

Starts the proxy, configures the agent's settings, and launches. The agent gets compression without any manual setup.

### Mode 3: Python/TypeScript Library

```python
from cutctx import compress

result = compress(messages, model="claude-sonnet-4-5")
response = client.messages.create(
    model="claude-sonnet-4-5",
    messages=result.messages,
)
print(f"Saved {result.tokens_saved} tokens ({result.compression_ratio:.0%})")
```

```typescript
import { compress } from 'cutctx-ai';
const result = await compress(messages, { model: 'claude-sonnet-4-5' });
```

### Mode 4: MCP Server

```bash
cutctx mcp install && claude
```

Installs three MCP tools into Claude Code: `cutctx_compress`, `cutctx_retrieve`, `cutctx_stats`. The agent can call them directly.

### Docker / Kubernetes

```bash
docker pull ghcr.io/cutctx/cutctx:latest
# Kubernetes: Helm charts available, see k8s/ directory
```

Full Helm deployment path for enterprise Kubernetes environments.

### Stateless Mode

For ephemeral / serverless deployments:

```bash
cutctx proxy --stateless
```

Zero files written to disk. All state in memory. SQLite uses `:memory:`. No beacon lock files, no file logging. Perfect for containers and CI.

### Air-Gap Mode

For environments with no internet access after initial setup:

```bash
CUTCTX_AIR_GAP=1 cutctx proxy
```

Requires `CUTCTX_LICENSE_HMAC_SECRET` to be set. Models pre-downloaded via `HF_HUB_OFFLINE=1`. Fully operational offline.

---

## 7. Agent Compatibility

| Agent | `cutctx wrap` | Notes |
|---|:---:|---|
| Claude Code | ✅ | `--memory` · `--code-graph` |
| OpenAI Codex CLI | ✅ | Shares memory with Claude |
| Cursor | ✅ | Prints config snippet — paste once |
| Aider | ✅ | Starts proxy + launches |
| GitHub Copilot CLI | ✅ | Starts proxy + launches; subscription mode supported |
| Windsurf | ✅ | Auto-configures settings.json |
| Zed | ✅ | Configures language_models API URLs |
| OpenCode | ✅ | Same pattern as Codex |
| OpenClaw | ✅ | Installs as ContextEngine plugin |
| Any OpenAI-compatible client | ✅ | via `cutctx proxy` |

### LLM Providers

Works with any provider via the proxy:

```bash
cutctx proxy                                          # Anthropic / OpenAI direct
cutctx proxy --backend bedrock --region us-east-1     # AWS Bedrock
cutctx proxy --backend vertex_ai --region us-central1 # Google Vertex AI
cutctx proxy --backend azure                          # Azure OpenAI
cutctx proxy --backend openrouter                     # OpenRouter (400+ models)
# Via LiteLLM callback: 100+ providers (Groq, Together, Fireworks, Ollama, vLLM, etc.)
```

---

## 8. Memory System

Cutctx includes a full hierarchical persistent memory system. This is **temporal compression** — instead of carrying 10,000 tokens of conversation history every request, you carry 100 tokens of extracted, relevant memories.

### Key Capability: Cross-Agent Memory

```bash
cutctx proxy --memory
cutctx wrap claude --memory    # Claude Code with memory
cutctx wrap codex --memory     # Codex uses the SAME memory store
```

**Claude saves a fact. Codex reads it back.** Any agent routing through the proxy shares one memory store. No other memory system does this.

### How Memory Works

1. **Inject:** On each request, Cutctx searches the memory DB semantically and injects relevant memories as system context — before the user message reaches the LLM.
2. **Extract:** The LLM's response is monitored for a `<memory>` block. Memories are extracted inline — **zero extra latency, zero extra API calls.**
3. **Deduplicate:** New memories are checked against existing ones. Cosine similarity >92% → auto-remove the duplicate. Between 60–92% → the LLM is given a hint to merge them.
4. **Store:** SQLite + HNSW vector index + FTS5 full-text index. Local, embedded, no external server needed.

### Hierarchical Scoping

```
USER (broadest — persists forever)
 └── SESSION (current session only)
      └── AGENT (current agent in session)
           └── TURN (single turn, ephemeral)
```

### Memory Categories

`PREFERENCE` · `FACT` · `CONTEXT` · `ENTITY` · `DECISION` · `INSIGHT`

### Temporal Versioning (Supersession)

When facts change, Cutctx creates a versioned supersession chain:
- "User works at Google" → superseded by → "User now works at Anthropic"
- Full history preserved with validity timestamps
- Query current state or full history

### Agent Provenance Tracking

Every memory records which agent created or updated it:
```json
{
  "content": "Project uses alembic for migrations",
  "metadata": {
    "source_agent": "claude",
    "source_provider": "anthropic",
    "created_via": "tool_call"
  }
}
```

### Performance

| Operation | Latency |
|---|---|
| Memory injection | <50ms |
| Memory extraction | +50–100 output tokens (inline) |
| Memory storage | <10ms |
| Cache hit | <1ms |

### vs. Competitors

| Feature | Cutctx | Letta (MemGPT) | Mem0 |
|---|:---:|:---:|:---:|
| Cross-agent sharing (proxy) | ✅ | ❌ | ❌ |
| Agent provenance tracking | ✅ | ❌ | ❌ |
| LLM dedup (no extra cost) | ✅ | ❌ | ❌ (separate LLM $) |
| Transparent proxy (zero code) | ✅ | ❌ | ❌ |
| Hierarchical scoping | ✅ | ❌ | ❌ |
| Temporal versioning | ✅ | ❌ | ❌ |
| Zero-latency extraction | ✅ | ✅ | ❌ |
| Full-text + semantic search | ✅ | ❌ | ❌ |
| Embedded (no server) | ✅ | ❌ | ❌ |

---

## 9. Cutctx Learn — Agent Self-Improvement

`cutctx learn` mines past agent sessions, finds failure patterns, correlates them with what eventually worked, and writes specific corrections to `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`.

**The core innovation:** Instead of just listing failures ("Read failed 5 times"), it finds the successful fix:

- **Failed:** `Read axion-formats/src/main/java/.../FirstClassEntity.java`
- **Then succeeded:** `Read axion-scala-common/src/main/scala/.../FirstClassEntity.scala`
- **Learning written to CLAUDE.md:** "`FirstClassEntity` is at `axion-scala-common/`, not `axion-formats/`"

### What It Learns

1. **Environment facts** — Which runtime commands work (e.g., "use `uv run python`, not `python3`")
2. **File path corrections** — Wrong paths the agent keeps guessing, with the correct locations
3. **Search scope** — Which directories to search in (narrow paths fail, broader ones work)
4. **Command patterns** — How commands should be run; commands the user repeatedly rejected
5. **Known large files** — Files that need `offset`/`limit` pagination

### Usage

```bash
cutctx learn              # Dry run — see recommendations, no changes
cutctx learn --apply      # Write recommendations to CLAUDE.md / AGENTS.md
cutctx learn --all        # Analyze all discovered projects
```

### Results (Real Data)

Tested on 67,583 tool calls across 23 projects:
- 7.5% failure rate (5,066 failures)
- 164 corrections extracted per project on average
- Estimated 27 MB of preventable wasted context across the corpus

---

## 10. Enterprise Features

Enterprise features are in the `cutctx_ee` module (compiled Cython `.so` binaries, HMAC-signed integrity manifest).

### SSO & Authentication

- JWT/JWKS token validation
- OIDC discovery endpoint support
- RFC 7662 token introspection
- Timing-safe claim validation
- MFA (TOTP)

### RBAC (Role-Based Access Control)

- Three roles: Viewer / Operator / Admin
- 15+ fine-grained permissions
- Wired into every admin API endpoint
- Persistent SQLite-backed with `:memory:` fallback for stateless mode

### Audit Logging

- SQLite WAL-backed structured event log
- Queryable with filters (time range, user, action type)
- JSONL export
- Retention controls (configurable retention window)

### SCIM Provisioning

- SCIM-style user/group provisioning APIs
- Central identity integration (connects to corporate directory)

### Fleet Management

- Fleet inventory APIs
- Multi-deployment monitoring from a single control plane
- Node management and health

### Multi-Tenant Org Structure

- Org → Workspace → Project hierarchy
- Per-workspace and per-project analytics
- Separate billing ledger per org

### LLM Firewall

- 27 regex patterns: injection attacks, PII detection, jailbreak attempts, data exfiltration
- Streaming redactor (catches sensitive data mid-stream)
- Structured output validation with 3× auto-retry on invalid JSON

### Billing & Entitlements

- 59-feature × 4-tier entitlement matrix (Builder / Team / Business / Enterprise)
- Runtime enforcement — enterprise features gated at import time
- Stripe integration for subscription management

### Security Hardening

- Hardware fingerprint: OS-native machine IDs (not MAC address)
- HMAC signatures: 128-bit, constant-time comparison
- Anti-debug guard: macOS `ptrace(PT_DENY_ATTACH)`, Linux TracerPid parse, Windows `IsDebuggerPresent`
- EE binary integrity manifest: SHA-256 hashes of all `.so` files, HMAC-signed, verified at startup
- Air-gap mode: proxy refuses to start without `CUTCTX_LICENSE_HMAC_SECRET`

---

## 11. Security & Privacy

### Data Handling

| Category | Default Handling |
|---|---|
| Prompt and response content | In-memory processing only — never logged or sent externally |
| Local retrieval state (CCR) | Customer-managed local storage |
| Admin audit records | Customer-managed local storage |
| Identity and org metadata | Customer-managed local storage |
| Telemetry | Aggregate counts only, opt-in, never message content |

### Local-First Architecture

- Cutctx runs **entirely on your infrastructure** — laptop, Docker, Kubernetes cluster
- Prompts never leave your network by default
- No cloud hop for compression — the algorithms run locally
- `--stateless` mode: zero files written to disk
- `--no-telemetry`: completely disables even aggregate telemetry

### What Cutctx Does NOT Do

- Does not log or store prompt content
- Does not send messages to Anthropic/Cutctx servers
- Does not require an internet connection after initial model download
- Does not use your data to train models

### Security Claims Supported Today

✅ Local-first deployment  
✅ No hosted prompt analytics requirement  
✅ SSO/JWT/OIDC admin authentication  
✅ RBAC  
✅ Audit logging with export  
✅ Retention controls  
✅ Fleet management APIs  
✅ SCIM-style provisioning  
✅ Kubernetes + Helm deployment  
✅ Air-gap compatible deployment path  

**What requires external validation:** SOC 2, formal DPA/MSA, third-party audit reports. Not available today but can be supported for lighthouse enterprise customers.

---

## 12. Integrations

### Framework Integrations

| Framework | Integration Type | Code |
|---|---|---|
| Python (any) | `compress()` function | `from cutctx import compress` |
| TypeScript / Node | `compress()` async function | `import { compress } from 'cutctx-ai'` |
| Anthropic SDK | Client wrapper | `CutctxAnthropicClient(client)` |
| OpenAI SDK | Client wrapper | `CutctxOpenAIClient(client)` |
| Vercel AI SDK | Middleware | `wrapLanguageModel({ model, middleware: cutctxMiddleware() })` |
| LiteLLM | Callback | `litellm.callbacks = [CutctxCallback()]` — covers 100+ providers |
| LangChain | Chat model wrapper | `CutctxChatModel(ChatOpenAI(...))` |
| Agno | Model wrapper | `CutctxAgnoModel(Claude(...))` |
| Strands | Model + hook provider | `CutctxStrandsModel(wrapped_model=bedrock_model)` |
| LlamaIndex | Node postprocessor | `CutctxNodePostprocessor()` |
| Langfuse | OTEL tracing | `cutctx proxy --langfuse` |
| ASGI apps | Middleware | `app.add_middleware(CompressionMiddleware)` |
| Multi-agent | Shared context | `SharedContext().put() / .get()` |

### Optional ML Extras

| Extra | What It Adds | Install |
|---|---|---|
| `[ml]` | Kompress-base neural compressor (ModernBERT) | `pip install "cutctx-ai[ml]"` |
| `[llmlingua]` | Microsoft LLMLingua-2 BERT compression | `pip install "cutctx-ai[llmlingua]"` |
| `[log-ml]` | Drain3 ML log template mining | `pip install "cutctx-ai[log-ml]"` |
| `[knowledge-graph]` | Graphify codebase graph | `pip install "cutctx-ai[knowledge-graph]"` |
| `[pytorch-mps]` | Apple GPU offload for embeddings | `pip install "cutctx-ai[pytorch-mps]"` |
| `[langchain]` | LangChain integration | `pip install "cutctx-ai[langchain]"` |
| `[agno]` | Agno integration | `pip install "cutctx-ai[agno]"` |
| `[image]` | Image compression | `pip install "cutctx-ai[image]"` |
| `[memory]` | Full memory system | `pip install "cutctx-ai[memory]"` |

---

## 13. Pricing & Tiers

### Tier Overview

| Tier | Monthly | Annual | Target |
|---|---|---|---|
| **Builder** | $0 | $0 | Individual engineers, OSS evaluators |
| **Team** | $1,500 | $18,000 | Single engineering team |
| **Business** | $3,500 | $42,000 | Platform teams, multi-project orgs |
| **Enterprise** | Custom | $60,000–$150,000+ | Security-sensitive, procurement-heavy |

Monthly billing available at 20% premium over annual.

### What Each Tier Includes

**Builder (Free)**
- Full compression pipeline (all 12 algorithms)
- Multimodal compression (images, audio)
- Cross-provider support
- Proxy, CLI wrap, SDK, MCP server
- Local dashboard
- Memory and CCR
- Docker deployment
- Community support (Discord)

**Team ($18k/year)**
- Everything in Builder, plus:
- Team analytics dashboard (`/analytics/dashboard`)
- Savings reports (`/reports/savings`, `/reports/usage`)
- Policy presets
- Budget controls
- Shared admin visibility
- Business-hours support

**Business ($42k/year)**
- Everything in Team, plus:
- Org → Workspace → Project management hierarchy
- Historical and exportable reporting
- Multi-project analytics
- Kubernetes manifests + Helm deployment
- Structured deployment advisory support

**Enterprise ($60k–$150k+/year)**
- Everything in Business, plus:
- SSO/OIDC/SAML admin authentication
- RBAC (Viewer / Operator / Admin roles)
- Audit logging with export
- Retention controls
- Fleet management APIs
- SCIM provisioning APIs
- Air-gap deployment support
- Security review packet
- Premium support + deployment hardening support

### Add-Ons

| Add-On | Price |
|---|---|
| Onboarding Package | $5,000 |
| Deployment Hardening (K8s/Helm review) | $3,000 |
| Premium SLA Upgrade (24/7, 1-hr critical SLA) | $10,000/year |
| Security Review Support | $7,500 |
| Custom Integration Work | Custom |

### Discount Rules

| Scenario | Discount | Approval Needed |
|---|---|---|
| Design partner | 30–40% | Founder |
| Multi-year term | 10–15% | Founder or sales lead |
| Lighthouse logo + case study | 15–25% | Founder |
| Competitive displacement | Up to 15% | Sales lead |
| Annual prepay | Included in list price | Standard |

**Floor:** Do not discount below 60% of list without explicit founder approval.

---

## 14. ROI & Business Case

### Four Value Dimensions

1. **Direct cost savings** — fewer tokens billed by LLM providers
2. **Context efficiency** — more usable context in finite windows; fewer context-limit errors
3. **Reliability** — fewer retries, faster agent runs, more reliable workflows
4. **Governance value** — team visibility, policy control, audit compliance

### Sample ROI Calculation

*Inputs: $15k/month LLM spend, 200 tool-output requests/day at 5,000 tokens each, $3/M token rate*

| Item | Monthly Value |
|---|---|
| Direct token savings (75% compression on tool outputs) | $675 |
| Retry cost reduction | $7 |
| Engineering time savings (34 hours/month at $125/hr) | $4,250 |
| **Total monthly savings** | **$4,932** |
| **Annual savings** | **$59,184** |
| Cutctx Team cost | $1,500/month |
| **Net annual benefit** | **$41,184** |
| **ROI** | **229%** |
| **Payback period** | **4.4 months** |

### Three Real Case Studies

**Case 1: Coding Agents (10-person team)**
- 10 engineers on Claude Code, 200 tool-output requests/day
- 85% compression on code search and diffs
- Monthly LLM spend: $12,000
- **Total monthly value: $8,900 → Annual ROI: 493%** (vs. Team tier $18k/year)

**Case 2: SRE / Ops Agent (24/7 incident response)**
- 5 agents, 100 incidents/day, 5,000–15,000 tokens of logs per incident
- 90% log compression
- Monthly LLM spend: $25,000
- **Total monthly value: $16,500 → Annual ROI: 680%** (vs. Business tier $42k/year)

**Case 3: Internal AI Platform (multi-team, multi-provider)**
- 50 engineers, 5 teams, Anthropic + OpenAI + Bedrock
- 75% average compression, cross-provider governance
- Monthly LLM spend: $40,000
- **Total monthly value: $22,000 → Annual ROI: 471%** (vs. Business tier $42k/year)

### Pricing Rule of Thumb

Target 10–20% of measurable annual customer value. If Cutctx saves $60k/year, $18k/year pricing (30%) is aggressive but fair for early lighthouse accounts.

### Savings Attribution (5 Independent Sources)

Cutctx never double-counts. Savings are attributed to exactly one of five sources:

1. **Provider prompt cache** — Anthropic `cache_read_input_tokens`, OpenAI `cached_tokens`
2. **Cutctx compression** — tokens removed by the compression pipeline
3. **Semantic cache** — prior near-duplicate request served from response cache
4. **Self-hosted prefix cache** — vLLM Automatic Prefix Caching
5. **Model routing** — cheaper model served instead of requested model

A buyer who already uses Anthropic prompt caching sees that on line 1, and Cutctx on line 2. They are independent, not redundant.

---

## 15. Competitive Landscape

| | Scope | Deployment | Local | Reversible | Cross-provider |
|---|---|---|:---:|:---:|:---:|
| **Cutctx** | All context — tools, RAG, logs, files, history, images | Proxy · library · middleware · MCP · wrap | ✅ | ✅ | ✅ |
| RTK | CLI command outputs | CLI wrapper | ✅ | ❌ | ❌ |
| lean-ctx | CLI commands, MCP tools, editor rules | CLI wrapper · MCP | ✅ | ❌ | ❌ |
| Compresr / Token Co. | Text sent to their API | Hosted API | ❌ | ❌ | Partial |
| OpenAI Compaction | Conversation history | Provider-native | ❌ | ❌ | ❌ (OpenAI only) |
| Morph Compact | Verbatim deletion | Hosted API | ❌ | ❌ | Partial |
| Manual optimization | Whatever you code | Engineering time | ✅ | Depends | Depends |

### Positioning Against Native Provider Caching

Native caching (Anthropic, OpenAI, Google) is a common objection. The answer:

> "Provider caching works on prefixes within one provider. Cutctx compresses tool outputs, logs, diffs, and code search — payloads native caching doesn't touch. We also add reversible retrieval, cross-provider coverage, team analytics, and governance. The two are complementary and tracked independently in the buyer report."

Key differences:
- Native caching: prefix-only, single provider, no governance, no tool output compression
- Cutctx: all content types, any provider, team visibility, policy control, reversible

---

## 16. Benchmarks & Proof Points

### Real Workloads

| Workload | Before | After | Savings |
|---|---:|---:|---:|
| Code search (100 results) | 17,765 tokens | 1,408 tokens | **92%** |
| SRE incident debugging | 65,694 tokens | 5,118 tokens | **92%** |
| GitHub issue triage | 54,174 tokens | 14,761 tokens | **73%** |
| Codebase exploration | 78,502 tokens | 41,254 tokens | **47%** |
| 100 production logs (1 FATAL) | 10,144 tokens | 1,260 tokens | **88%** |

The log example is the most compelling demo: 10,144 tokens down to 1,260 — **88% smaller, same FATAL error found.** The error was preserved not by keyword matching but by statistical analysis of field variance.

### Accuracy Benchmarks (No Quality Loss)

| Benchmark | Category | N | Baseline | Cutctx | Delta |
|---|---|---|---:|---:|---|
| GSM8K | Math | 100 | 0.870 | 0.870 | **±0.000** |
| TruthfulQA | Factual | 100 | 0.530 | 0.560 | **+0.030** |
| SQuAD v2 | QA | 100 | — | 97% | 19% compression |
| BFCL | Tool/Function | 100 | — | 97% | 32% compression |
| CCR Needle | Lossless retrieval | 50 | — | 100% | 77% reduction |

Math accuracy is **unchanged.** Factual accuracy actually **improves** (less noise = better signal). Tool calling is 97% accurate at 32% compression.

Reproduce: `python -m cutctx.evals suite --tier 1`

### Technical Specs

- Rust core: sub-millisecond compression
- 1,000+ automated tests
- 157/157 manual testing guide steps pass
- 335+ test files across the test suite

---

## 17. Installation & Setup

### Prerequisites

- Python 3.10+
- pip or uv

### Basic Install

```bash
pip install "cutctx-ai[all]"    # Everything
pip install cutctx-ai           # Core library only
npm install cutctx-ai           # TypeScript / Node
```

### Granular Extras

```bash
pip install "cutctx-ai[proxy]"      # Proxy server + MCP tools
pip install "cutctx-ai[ml]"         # Kompress neural compression
pip install "cutctx-ai[code]"       # AST-aware code compression
pip install "cutctx-ai[memory]"     # Persistent memory system
pip install "cutctx-ai[langchain]"  # LangChain integration
pip install "cutctx-ai[agno]"       # Agno integration
pip install "cutctx-ai[image]"      # Image compression
pip install "cutctx-ai[evals]"      # Evaluation framework
pip install "cutctx-ai[pytorch-mps]" # Apple GPU (M-series)
```

### Agent Setup (Claude Code — Global)

To route all Claude Code sessions through Cutctx regardless of project:

```bash
cd /path/to/cutctx
.venv/bin/cutctx wrap claude
```

This writes `ANTHROPIC_BASE_URL=http://127.0.0.1:8787` to `~/.claude/settings.json`.

### Key Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_BASE_URL` | Point Claude at Cutctx proxy |
| `OPENAI_BASE_URL` | Point OpenAI-compatible clients at proxy |
| `CUTCTX_ACCURACY_GUARD` | `strict` / `balanced` / `off` |
| `CUTCTX_STATELESS` | `true` = zero files written |
| `CUTCTX_AIR_GAP` | `1` = air-gap mode |
| `CUTCTX_EMBEDDER_RUNTIME` | `pytorch_mps` for Apple GPU |
| `HF_HUB_OFFLINE` | `1` = offline model loading |
| `CUTCTX_LICENSE_HMAC_SECRET` | Enterprise license key |

---

## 18. Sales Objection Handling

### "We already use provider-native caching"

> "That's great — native caching handles prefix caching within a single provider. Cutctx is complementary: it compresses tool outputs, logs, diffs, and code search results that native caching doesn't touch at all. We also add reversible retrieval, cross-provider analytics, and team governance that no provider offers. Both show up as separate line items in our buyer report — they're additive, not redundant."

### "We don't want to send prompts to another SaaS"

> "Cutctx runs locally by default — in your laptop, Docker container, or Kubernetes cluster. Your prompts never leave your infrastructure. We're not a cloud service — we're a local proxy. There's nothing to 'send to us.'"

### "Our LLM spend isn't that high yet"

> "Cutctx is most valuable when agents read large tool outputs — code search results, logs, file diffs. Even moderate spend compounds fast when every agent loop reads 5,000–15,000 tokens of tool output per request. We typically see 60–92% reduction on those payloads. At $5k/month, 75% compression on tool outputs is still $3k+/month saved. And as AI usage grows, savings scale proportionally — Cutctx cost stays flat."

### "We're worried compression will hurt quality"

> "Cutctx uses reversible compression — CCR. The original payloads are stored locally and retrievable on demand via a tool call. The LLM can always get the full original if it needs it. We also run accuracy guards before forwarding. Our benchmarks show zero accuracy loss on math (GSM8K), factual improvement on TruthfulQA (+0.030), and 97% tool-calling accuracy at 32% compression. You can start with `--accuracy-guard strict` and dial it back as you get confident."

### "We only use one provider"

> "Cutctx still adds significant value on a single provider: tool output compression (which provider caching doesn't touch), reversible retrieval, the memory system, failure learning, team analytics, and governance. And when you inevitably add a second provider — Bedrock for cost, OpenAI for a specific model — you're already set up with a single layer across all of them."

### "We have security/compliance requirements"

> "Cutctx was designed for this. Self-hosted, local-first, no data leaves your infrastructure. Enterprise tier includes SSO/SAML, RBAC, audit logs, retention controls, SCIM provisioning, and air-gap deployment support. We can provide a security review packet for your procurement team. We don't have SOC 2 today — that's something we can pursue together for a lighthouse enterprise customer."

### "Why not just use the native /v1/messages compression endpoint?"

> "Provider-native compaction works on conversation history only. Cutctx compresses tool outputs, logs, code search, file reads, diffs — the stuff that actually drives agent token spend. Plus we're cross-provider, reversible, local, and add team analytics and governance that no provider offers."

### "How is this different from just truncating context?"

> "Truncation throws away content blindly. Cutctx is content-aware: it detects what type of data is in each message (JSON, code, logs, prose), picks the best algorithm for it, compresses the redundant parts while preserving signal, and keeps the originals locally for retrieval. The LLM sees less, but what it sees is more information-dense."

---

## 19. Pitch by Audience

### Individual Developer / Startup Engineer

> "Your AI coding agent is burning tokens on verbose tool outputs and logs. Cutctx compresses them by 60–95% with zero code changes — one command and you're done. Same answers, fraction of the cost. Free tier, install in 60 seconds: `pip install 'cutctx-ai[all]' && cutctx wrap claude`."

### Engineering Team Lead

> "Your team runs Claude Code or Codex daily. Token bills are growing with every sprint. Cutctx cuts tool output costs by 60–92%, adds shared memory across agents, and shows you exactly where your AI spend goes. Team tier is $18k/year — typically pays back in under 5 months."

### Platform Engineering / DevTools

> "You're building AI agent infrastructure across multiple providers and teams. Cutctx is a single context optimization layer that works across Anthropic, OpenAI, Bedrock, and Vertex — with team analytics, policy presets, reversible retrieval, and cross-agent memory. Runs in your Kubernetes cluster. No vendor lock-in. Business tier at $42k/year."

### Enterprise Security / Procurement

> "Cutctx is a self-hosted proxy. Your prompts never leave your network. Enterprise tier includes SSO/SAML, RBAC, audit logs with export, retention controls, SCIM provisioning, and air-gap deployment support. We can provide a security review packet for your team. Pricing starts at $60k/year, tailored to your deployment size."

### CFO / Finance

> "We're spending $X/month on AI APIs. Cutctx cuts that by 60–92% on tool-heavy workloads with zero code changes. At $15k/month spend, we save ~$4,900/month — $59k/year — against a $18k/year subscription. 229% ROI, 4.4-month payback. As our AI usage grows, savings scale proportionally while the Cutctx cost stays flat."

---

## 20. Quick-Reference FAQ

**Q: Does Cutctx work with Claude Code / Cursor / Codex out of the box?**  
A: Yes. `cutctx wrap claude` (or `cursor`, `codex`, etc.) starts the proxy and configures the agent in one command.

**Q: Do I need to change my code?**  
A: No. The proxy mode is zero code changes — just point `ANTHROPIC_BASE_URL` or `OPENAI_BASE_URL` at the proxy.

**Q: Where does my data go?**  
A: Nowhere except your LLM provider. Cutctx processes everything locally. No data is sent to Cutctx servers.

**Q: What if compression makes the LLM miss something important?**  
A: CCR (reversible compression) stores originals locally. The LLM has a `cutctx_retrieve` tool and can fetch the full original anytime. Nothing is permanently discarded.

**Q: Does it work with Bedrock / Vertex / Azure?**  
A: Yes. `cutctx proxy --backend bedrock`, `--backend vertex_ai`, `--backend azure`. Or via LiteLLM for 100+ providers.

**Q: How is this different from OpenAI's native context compaction?**  
A: OpenAI compaction handles conversation history only. Cutctx handles tool outputs, logs, code search, diffs — the bulk of agent token spend. Plus it's cross-provider, reversible, and local.

**Q: Can multiple agents share memory?**  
A: Yes. `cutctx proxy --memory` creates a shared store. Claude saves a fact; Codex reads it. Any agent routing through the proxy shares one store.

**Q: What's the accuracy impact?**  
A: GSM8K (math): ±0.000 delta. TruthfulQA: +0.030 improvement. SQuAD v2: 97% at 19% compression. BFCL (tool calling): 97% at 32% compression. CCR lossless retrieval: 100%.

**Q: How do I see what it's saving?**  
A: `cutctx perf` shows savings breakdown. `http://localhost:8787/stats` shows the live dashboard. `cutctx report buyer --format json` shows a full attributable breakdown.

**Q: Can it run air-gapped?**  
A: Yes. Download the models once (`HF_HUB_OFFLINE=1`), set `CUTCTX_AIR_GAP=1`, set `CUTCTX_LICENSE_HMAC_SECRET`. Fully offline after that.

**Q: What's the overhead / latency?**  
A: Sub-millisecond compression (Rust core). Memory injection adds <50ms. The latency Cutctx adds is far smaller than the latency savings from sending 80% fewer tokens to the LLM.

**Q: Is there a free tier?**  
A: Yes. Builder tier is free, forever. Full compression pipeline, all algorithms, proxy, SDK, MCP, memory, CCR. No time limit. The paid tiers add team analytics, governance, and enterprise features.

**Q: What language/runtime is Cutctx?**  
A: Python library with a Rust core for performance-critical compression. TypeScript SDK available separately. Python 3.10+ required.

**Q: Does it support multi-tenant enterprise deployments?**  
A: Yes. Enterprise tier includes Org → Workspace → Project hierarchy, RBAC, SCIM provisioning, fleet management, audit logs, and Helm deployment.

---

*Last updated: June 2026 — based on v0.26.x / v0.27.0 codebase*
